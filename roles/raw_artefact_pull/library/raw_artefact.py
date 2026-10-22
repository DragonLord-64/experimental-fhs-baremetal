import base64
import grp
import hashlib
import json
import os
import pwd
import shutil
import tarfile
import tempfile
import urllib.request
from json import JSONDecodeError
from urllib.parse import urlencode, urlsplit
from urllib.error import HTTPError, URLError

from ansible.module_utils.basic import AnsibleModule

MANIFEST_ACCEPT = (
    "application/vnd.oci.image.manifest.v1+json, "
    "application/vnd.docker.distribution.manifest.v2+json"
)


def describe_http_error(error):
    try:
        body = error.read()
    except Exception:
        body = None
    detail = body.decode("utf-8", errors="replace").strip() if body else None
    message = "HTTP Error {code}: {reason} for {url}".format(
        code=error.code, reason=error.reason, url=error.url
    )
    if detail:
        message = "{message} - {detail}".format(message=message, detail=detail)
    return message


DOCUMENTATION = r"""
---
module: raw_artefact
short_description: Pull and unpack OCI artefacts
description:
  - Pull a generic OCI artefact from a registry and unpack it onto the target
    host.
  - This step fetches and parses the manifest, then stops before blob download.
options:
  registry:
    description:
      - Registry hostname, optionally including a port.
    required: true
    type: str
  repository:
    description:
      - Repository path inside the registry.
    required: true
    type: str
  reference:
    description:
      - Tag or digest reference for the artefact.
    required: true
    type: str
  dest_path:
    description:
      - Target unpack directory on the managed host.
    required: true
    type: path
  owner:
    description:
      - Owner to apply recursively after unpacking.
    type: str
  group:
    description:
      - Group to apply recursively after unpacking.
    type: str
  mode:
    description:
      - Mode to apply recursively after unpacking.
    type: str
  create:
    description:
      - Create C(dest_path) if it does not exist.
    type: bool
    default: false
  username:
    description:
      - Optional registry username.
    type: str
  password:
    description:
      - Optional registry password.
    type: str
  http_proxy:
    description:
      - HTTP proxy override for this request.
    type: str
  https_proxy:
    description:
      - HTTPS proxy override for this request.
    type: str
  no_proxy:
    description:
      - No-proxy override for this request.
    type: str
  registry_mirror:
    description:
      - Registry mirror host to use instead of C(registry).
    type: str
  tls_verify:
    description:
      - Whether to use HTTPS (true) or HTTP (false) when connecting to
        the registry. Controls scheme selection for test/mirror registries
        only; does not perform certificate validation or verification.
    type: bool
    default: true
  timeout:
    description:
      - HTTP request timeout in seconds.
    type: int
    default: 30
author:
  - GitHub Copilot
"""

EXAMPLES = r"""
---
- name: Pull an OCI artefact
  raw_artefact:
    registry: registry.example.com
    repository: myorg/myapp-config
    reference: v1.2.3
    dest_path: /opt/myapp/config
    create: true
    owner: myapp
    group: myapp
    mode: "0750"

- name: Pull through a mirror with credentials
  raw_artefact:
    registry: registry.example.com
    repository: myorg/private-data
    reference: "sha256:abc123..."
    dest_path: /opt/myapp/data
    username: "{{ vault_registry_user }}"
    password: "{{ vault_registry_pass }}"
    registry_mirror: cache.internal.example.com
    https_proxy: http://proxy.example.com:3128
"""

RETURN = r"""
changed:
  description: Whether the module changed the target host.
  returned: always
  type: bool
digest:
  description: Resolved manifest digest for the pulled artefact.
  returned: when implemented
  type: str
msg:
  description: Summary message from the module.
  returned: always
  type: str
"""


def build_argument_spec():
    return {
        "registry": {"type": "str", "required": True},
        "repository": {"type": "str", "required": True},
        "reference": {"type": "str", "required": True},
        "dest_path": {"type": "path", "required": True},
        "owner": {"type": "str"},
        "group": {"type": "str"},
        "mode": {"type": "str"},
        "create": {"type": "bool", "default": False},
        "username": {"type": "str", "no_log": True},
        "password": {"type": "str", "no_log": True},
        "http_proxy": {"type": "str"},
        "https_proxy": {"type": "str"},
        "no_proxy": {"type": "str"},
        "registry_mirror": {"type": "str"},
        "tls_verify": {"type": "bool", "default": True},
        "timeout": {"type": "int", "default": 30},
    }


def validate_params(module):
    if module.params["reference"].strip() == "":
        module.fail_json(msg="reference must be a non-empty string")


def host_matches_no_proxy(host, no_proxy):
    hostname = urlsplit("//{host}".format(host=host)).hostname
    hostname = (hostname or host).lower()

    for entry in no_proxy.split(","):
        candidate = entry.strip()
        if not candidate:
            continue
        if candidate == "*":
            return True

        candidate_host = urlsplit("//{host}".format(host=candidate)).hostname
        candidate_host = (candidate_host or candidate).lower().lstrip(".")
        if (
            hostname == candidate_host
            or hostname.endswith(".{0}".format(candidate_host))
        ):
            return True

    return False


class ArchiveExtractionError(Exception):
    """Raised when a layer looks like an archive by filename but isn't
    unpackable as gzip-tar or plain tar (e.g. an unsupported compression,
    or a filename/content mismatch)."""


class NoProxyHandler(urllib.request.ProxyHandler):
    def __init__(self, proxies, no_proxy):
        super().__init__(proxies)
        self.no_proxy = no_proxy

    def proxy_open(self, req, proxy, request_type):
        if req.host and host_matches_no_proxy(req.host, self.no_proxy):
            return None
        return super().proxy_open(req, proxy, request_type)


class CrossHostSafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Strip Authorization on redirect to a different host.

    Registries backed by S3 (e.g. Harbor) redirect blob downloads to a
    presigned S3 URL with its own auth baked into the query string.
    urllib's default redirect handling forwards the original request's
    Authorization header regardless of host, which S3 rejects outright
    ("Only one auth mechanism allowed").
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        new_request = super().redirect_request(
            req, fp, code, msg, headers, newurl
        )
        if new_request is None:
            return None
        if urlsplit(req.full_url).hostname != urlsplit(newurl).hostname:
            new_request.remove_header("Authorization")
        return new_request


def build_opener(http_proxy=None, https_proxy=None, no_proxy=None):
    proxies = {}
    if http_proxy:
        proxies["http"] = http_proxy
    if https_proxy:
        proxies["https"] = https_proxy

    if no_proxy:
        proxy_handler = NoProxyHandler(proxies or {}, no_proxy)
    else:
        proxy_handler = urllib.request.ProxyHandler(proxies or None)
    return urllib.request.build_opener(
        proxy_handler, CrossHostSafeRedirectHandler()
    )


def build_manifest_request(
    host, repository, reference, token=None, tls_verify=True
):
    headers = {"Accept": MANIFEST_ACCEPT}
    if token:
        headers["Authorization"] = "Bearer {token}".format(token=token)

    scheme = "https" if tls_verify else "http"
    url = "{scheme}://{host}/v2/{repository}/manifests/{reference}"
    return urllib.request.Request(
        url.format(
            scheme=scheme,
            host=host,
            repository=repository,
            reference=reference,
        ),
        headers=headers,
        method="GET",
    )


def build_blob_request(
    host, repository, digest, token=None, tls_verify=True
):
    headers = {}
    if token:
        headers["Authorization"] = "Bearer {token}".format(token=token)

    scheme = "https" if tls_verify else "http"
    url = "{scheme}://{host}/v2/{repository}/blobs/{digest}"
    return urllib.request.Request(
        url.format(
            scheme=scheme,
            host=host,
            repository=repository,
            digest=digest,
        ),
        headers=headers,
        method="GET",
    )


def parse_www_authenticate(header_value):
    if not header_value:
        raise ValueError("WWW-Authenticate header is required for bearer auth")

    scheme, _, params = header_value.strip().partition(" ")
    if scheme.lower() != "bearer":
        raise ValueError("WWW-Authenticate scheme must be Bearer")

    parsed = {}
    for item in params.split(","):
        chunk = item.strip()
        if not chunk:
            continue
        key, separator, value = chunk.partition("=")
        if not separator:
            continue
        key = key.strip().lower()
        value = value.strip().strip('"')
        if value:
            parsed[key] = value

    if "realm" not in parsed:
        raise ValueError("WWW-Authenticate Bearer challenge is missing realm")

    return parsed


def get_bearer_token(
    opener,
    realm,
    service,
    scope,
    username,
    password,
    timeout,
):
    query = {}
    if service:
        query["service"] = service
    if scope:
        query["scope"] = scope

    token_url = realm
    if query:
        separator = "&" if "?" in realm else "?"
        token_url = "{realm}{separator}{query}".format(
            realm=realm,
            separator=separator,
            query=urlencode(query),
        )

    headers = {}
    if username is not None and password is not None:
        credentials = "{username}:{password}".format(
            username=username,
            password=password,
        )
        encoded = base64.b64encode(credentials.encode("utf-8")).decode("ascii")
        headers["Authorization"] = "Basic {encoded}".format(encoded=encoded)

    request = urllib.request.Request(token_url, headers=headers, method="GET")
    with opener.open(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))

    token = payload.get("token") or payload.get("access_token")
    if not token:
        raise ValueError(
            "token response did not contain token or access_token"
        )

    return token


def open_with_bearer_auth(
    opener,
    request,
    timeout,
    username=None,
    password=None,
):
    request_with_auth = request
    if username is not None and password is not None:
        auth_str = base64.b64encode(
            f"{username}:{password}".encode()
        ).decode("ascii")
        headers = dict(request.header_items())
        headers["Authorization"] = f"Basic {auth_str}"
        request_with_auth = urllib.request.Request(
            request.full_url,
            data=request.data,
            headers=headers,
            method=request.get_method(),
        )

    try:
        return opener.open(request_with_auth, timeout=timeout)
    except HTTPError as error:
        if error.code != 401:
            raise

        auth_header = error.headers.get("WWW-Authenticate")
        auth_params = parse_www_authenticate(auth_header)
        token = get_bearer_token(
            opener=opener,
            realm=auth_params["realm"],
            service=auth_params.get("service"),
            scope=auth_params.get("scope"),
            username=username,
            password=password,
            timeout=timeout,
        )
        retry_headers = dict(request.header_items())
        retry_headers["Authorization"] = "Bearer {token}".format(token=token)
        retry_request = urllib.request.Request(
            request.full_url,
            data=request.data,
            headers=retry_headers,
            method=request.get_method(),
        )
        return opener.open(retry_request, timeout=timeout)


def fetch_manifest(
    opener,
    host,
    repository,
    reference,
    timeout,
    username=None,
    password=None,
    tls_verify=True,
):
    request = build_manifest_request(
        host, repository, reference, tls_verify=tls_verify
    )
    with open_with_bearer_auth(
        opener=opener,
        request=request,
        timeout=timeout,
        username=username,
        password=password,
    ) as response:
        return json.loads(response.read().decode("utf-8"))


def download_blob(
    opener,
    host,
    repository,
    digest,
    timeout,
    username=None,
    password=None,
    tls_verify=True,
):
    request = build_blob_request(
        host, repository, digest, tls_verify=tls_verify
    )
    sha256 = hashlib.sha256()
    temp_path = None

    try:
        with open_with_bearer_auth(
            opener=opener,
            request=request,
            timeout=timeout,
            username=username,
            password=password,
        ) as response:
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_path = temp_file.name
                while True:
                    chunk = response.read(65536)
                    if not chunk:
                        break
                    sha256.update(chunk)
                    temp_file.write(chunk)

        actual_digest = "sha256:{digest}".format(digest=sha256.hexdigest())
        if actual_digest != digest:
            os.unlink(temp_path)
            raise ValueError(
                (
                    "digest mismatch for blob {expected}: expected "
                    "{expected}, got {actual}"
                ).format(
                    expected=digest,
                    actual=actual_digest,
                )
            )

        return temp_path
    except Exception:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)
        raise


def collect_written_paths(dest_root, target_path):
    written_paths = {target_path}
    parent = os.path.dirname(target_path)

    while (
        parent != dest_root
        and os.path.commonpath([dest_root, parent]) == dest_root
    ):
        if os.path.exists(parent):
            break
        written_paths.add(parent)
        parent = os.path.dirname(parent)

    return written_paths


def resolve_within_dest(dest_path, relative_path):
    dest_root = os.path.realpath(dest_path)
    # Archives commonly carry absolute-path members (e.g. built via
    # `tar -C / -cf archive.tar /some/path`); GNU tar and Python's own
    # tarfile extraction filters strip the leading slash and treat them
    # as relative to the extraction directory rather than rejecting them
    # outright. The traversal check below still applies to the stripped
    # name, so this doesn't weaken the guard against `../`-style escapes.
    normalized = relative_path.lstrip("/")
    target_path = os.path.realpath(os.path.join(dest_root, normalized))
    if os.path.commonpath([dest_root, target_path]) != dest_root:
        raise ValueError(
            (
                "path traversal detected: member '{name}' escapes "
                "dest_path"
            ).format(name=relative_path)
        )
    return target_path


def _sanitize_extracted_mode(member, dest_path):
    # safe_tar_extract has already validated every member name and
    # symlink/hardlink target, treating a leading '/' as root-relative
    # (see resolve_within_dest). Strip it here too so the actual
    # extraction agrees with that interpretation -- otherwise tarfile
    # would extract an absolute-path member to that literal path on the
    # real filesystem instead of under dest_path.
    replacements = {}
    if member.name.startswith("/"):
        replacements["name"] = member.name.lstrip("/")

    if member.issym() and member.linkname.startswith("/"):
        # os.symlink() uses linkname completely literally -- an absolute
        # target isn't reinterpreted as root-relative by the OS the way
        # we treat it above, it would create a symlink pointing outside
        # dest_path (almost certainly nonexistent there). Rewrite it as a
        # relative path from the symlink's own (already-rewritten)
        # location to the same root-relative target we already validated
        # in safe_tar_extract, so it resolves correctly under dest_path.
        target = member.linkname.lstrip("/")
        symlink_dir = os.path.dirname(replacements.get("name", member.name))
        replacements["linkname"] = os.path.relpath(
            target, start=symlink_dir or "."
        )
    elif member.islnk() and member.linkname.startswith("/"):
        # Hardlink targets are resolved as os.path.join(dest_path,
        # linkname) (tarfile.py's _link_target), so simply stripping the
        # leading slash is enough for it to land under dest_path -- unlike
        # symlinks, this isn't relative to the hardlink's own directory.
        replacements["linkname"] = member.linkname.lstrip("/")

    if member.isdir() or member.issym():
        # Tar-encoded mode for a directory/symlink is often nonsensical
        # (e.g. missing the execute bit needed to traverse it); ignore it
        # and let the OS apply its own default.
        if member.mode is not None:
            replacements["mode"] = None
    elif member.isreg() or member.islnk():
        mode = member.mode
        if mode is not None:
            mode &= 0o755
            if not mode & 0o100:
                mode &= ~0o111
            mode |= 0o600
            if mode != member.mode:
                replacements["mode"] = mode

    return member.replace(**replacements) if replacements else member


def safe_tar_extract(tar_obj, dest_path, members=None):
    dest_root = os.path.realpath(dest_path)
    if members is None:
        members = tar_obj.getmembers()
    written_paths = set()

    for member in members:
        member_path = resolve_within_dest(dest_root, member.name)
        written_paths.update(collect_written_paths(dest_root, member_path))
        if member.issym():
            link_base = os.path.dirname(member.name)
            resolve_within_dest(
                dest_root,
                os.path.join(link_base, member.linkname),
            )
        if member.islnk():
            resolve_within_dest(dest_root, member.linkname)

    # We've already validated every member name and symlink/hardlink
    # target above (including absolute ones, treated as root-relative),
    # so tarfile's own path-safety filtering would be redundant. But its
    # default filter on Python 3.12+ (PEP 706) also outright rejects any
    # symlink/hardlink with an absolute target, and its permissive 'tar'
    # filter instead preserves whatever mode an archive encoded for a
    # directory -- which can leave it non-traversable (e.g. mode 0o644,
    # no execute bit). Use a filter that only sanitizes modes (ignoring
    # tar-encoded mode for dirs/symlinks, same as the 'data' filter)
    # without re-checking paths. Older Python versions have no filter
    # concept at all, so this is a no-op there.
    if hasattr(tarfile, "tar_filter"):
        tar_obj.extraction_filter = _sanitize_extracted_mode
    tar_obj.extractall(dest_path, members=members)
    return written_paths


def extract_archive(blob_path, dest_path, try_gzip=True):
    if try_gzip:
        gz_tar = None
        try:
            gz_tar = tarfile.open(blob_path, mode="r:gz")
            members = gz_tar.getmembers()
        except (OSError, tarfile.TarError):
            if gz_tar is not None:
                gz_tar.close()
        else:
            with gz_tar:
                return safe_tar_extract(
                    gz_tar,
                    dest_path,
                    members=members,
                )

    try:
        with tarfile.open(blob_path, mode="r:") as tar_obj:
            return safe_tar_extract(tar_obj, dest_path)
    except (OSError, tarfile.TarError) as error:
        raise ArchiveExtractionError(
            "could not unpack '{name}' as a tar archive: {error}".format(
                name=os.path.basename(blob_path), error=error
            )
        )


def place_file(blob_path, dest_path, filename):
    target_path = resolve_within_dest(dest_path, filename)
    shutil.copyfile(blob_path, target_path)
    return collect_written_paths(os.path.realpath(dest_path), target_path)


def apply_ownership_permissions(written_paths, owner=None, group=None,
                                mode=None):
    if not owner and not group and not mode:
        return

    uid = None
    gid = None

    if owner:
        try:
            uid = pwd.getpwnam(owner).pw_uid
        except KeyError:
            msg = "owner '{owner}' does not exist".format(owner=owner)
            raise ValueError(msg)

    if group:
        try:
            gid = grp.getgrnam(group).gr_gid
        except KeyError:
            msg = "group '{group}' does not exist".format(group=group)
            raise ValueError(msg)

    mode_int = None
    if mode:
        try:
            mode_int = int(mode, 8)
        except ValueError:
            msg = (
                "mode '{mode}' is not a valid octal string"
                .format(mode=mode)
            )
            raise ValueError(msg)

    for path in written_paths:
        is_symlink = os.path.islink(path)
        if uid is not None or gid is not None:
            # os.chown's follow_symlinks=False (lchown) changes the
            # symlink's own ownership without ever touching its target --
            # required since a symlink extracted from an archive may be
            # dangling (its target need not exist under dest_path).
            os.chown(
                path,
                uid if uid is not None else -1,
                gid if gid is not None else -1,
                follow_symlinks=False,
            )
        if mode_int is not None and not is_symlink:
            # Symlink permission bits are meaningless on Linux (lchmod
            # isn't supported), and os.chmod()'s default follow_symlinks
            # would otherwise try to chmod a possibly-nonexistent target.
            # GNU chmod -R skips symlinks for the same reason.
            os.chmod(path, mode_int)


def compute_composite_digest(parsed_layers):
    sha256 = hashlib.sha256()
    sorted_digests = sorted([layer["digest"] for layer in parsed_layers])
    for digest in sorted_digests:
        sha256.update(digest.encode("utf-8"))
    return "sha256:{digest}".format(digest=sha256.hexdigest())


def get_marker_path(dest_path):
    return os.path.join(dest_path, ".raw_artefact_state.json")


def load_marker(dest_path):
    marker_path = get_marker_path(dest_path)
    if not os.path.exists(marker_path):
        return None
    try:
        with open(marker_path, "r") as f:
            return json.load(f)
    except (IOError, json.JSONDecodeError):
        return None


def write_marker(dest_path, composite_digest, parsed_layers, reference,
                 owner, group, mode):
    marker_data = {
        "composite_digest": composite_digest,
        "reference": reference,
        "owner": owner,
        "group": group,
        "mode": mode,
        "layers": [
            {"filename": layer["filename"], "digest": layer["digest"]}
            for layer in parsed_layers
        ],
    }
    marker_path = get_marker_path(dest_path)
    with open(marker_path, "w") as f:
        json.dump(marker_data, f)


def get_path_stat(path):
    try:
        stat_info = os.stat(path)
        return {
            "uid": stat_info.st_uid,
            "gid": stat_info.st_gid,
            "mode": stat_info.st_mode & 0o7777,
        }
    except OSError:
        return None


def ownership_mode_match(dest_path, owner, group, mode):
    stat_info = get_path_stat(dest_path)
    if stat_info is None:
        return False

    if owner:
        try:
            expected_uid = pwd.getpwnam(owner).pw_uid
            if stat_info["uid"] != expected_uid:
                return False
        except KeyError:
            return False

    if group:
        try:
            expected_gid = grp.getgrnam(group).gr_gid
            if stat_info["gid"] != expected_gid:
                return False
        except KeyError:
            return False

    if mode:
        try:
            expected_mode = int(mode, 8) & 0o7777
            if stat_info["mode"] != expected_mode:
                return False
        except ValueError:
            return False

    return True


def is_archive_layer(filename):
    lowered = filename.lower()
    return (
        lowered.endswith(".tar.gz")
        or lowered.endswith(".tgz")
        or lowered.endswith(".tar")
    )


def parse_layers(manifest_json):
    layers = manifest_json.get("layers")
    if not layers:
        raise ValueError("manifest must contain at least one layer")

    parsed_layers = []
    for index, layer in enumerate(layers):
        annotations = layer.get("annotations") or {}
        filename = annotations.get("org.opencontainers.image.title")
        if not filename:
            digest = layer.get("digest", "<unknown digest>")
            raise ValueError(
                "layer {index} ({digest}) is missing "
                "annotations.org.opencontainers.image.title".format(
                    index=index,
                    digest=digest,
                )
            )

        parsed_layers.append(
            {
                "filename": filename,
                "digest": layer["digest"],
                "size": layer["size"],
            }
        )

    return parsed_layers


def run_module():
    module = AnsibleModule(
        argument_spec=build_argument_spec(),
        supports_check_mode=True,
    )
    validate_params(module)
    downloaded_layers = []
    written_paths = set()
    changed = True

    try:
        dest_path = module.params["dest_path"]

        # Handle dest_path creation before any layer dispatch
        if not os.path.isdir(dest_path):
            if module.params["create"]:
                # Only actually create in non-check-mode
                if not module.check_mode:
                    os.makedirs(dest_path, exist_ok=True)
                    written_paths.add(dest_path)
            else:
                raise FileNotFoundError(
                    (
                        "dest_path '{dest_path}' does not exist. "
                        "Set create to true or pre-create the path."
                    ).format(dest_path=dest_path)
                )

        host = module.params["registry_mirror"] or module.params["registry"]
        opener = build_opener(
            http_proxy=module.params["http_proxy"],
            https_proxy=module.params["https_proxy"],
            no_proxy=module.params["no_proxy"],
        )
        manifest_json = fetch_manifest(
            opener=opener,
            host=host,
            repository=module.params["repository"],
            reference=module.params["reference"],
            timeout=module.params["timeout"],
            username=module.params["username"],
            password=module.params["password"],
            tls_verify=module.params["tls_verify"],
        )
        parsed_layers = parse_layers(manifest_json)

        # Compute composite digest before any downloads (for idempotency)
        composite_digest = compute_composite_digest(parsed_layers)

        # Check idempotency: marker + owner/mode match = skip downloads
        marker = load_marker(dest_path)
        if (
            marker is not None
            and marker.get("composite_digest") == composite_digest
            and marker.get("owner") == module.params["owner"]
            and marker.get("group") == module.params["group"]
            and marker.get("mode") == module.params["mode"]
            and ownership_mode_match(
                dest_path,
                module.params["owner"],
                module.params["group"],
                module.params["mode"],
            )
        ):
            # Fast path: no changes needed
            changed = False
            module.exit_json(changed=changed, msg="artefact already deployed")
            return

        # If check_mode, determine changed without actually downloading
        if module.check_mode:
            changed = True
            module.exit_json(
                changed=changed,
                msg="would deploy artefact (check mode)"
            )
            return

        # Download and process layers
        for layer in parsed_layers:
            blob_path = download_blob(
                opener=opener,
                host=host,
                repository=module.params["repository"],
                digest=layer["digest"],
                timeout=module.params["timeout"],
                username=module.params["username"],
                password=module.params["password"],
                tls_verify=module.params["tls_verify"],
            )
            downloaded_layers.append((layer, blob_path))

        # Process layers and collect written paths
        for layer, blob_path in downloaded_layers:
            if is_archive_layer(layer["filename"]):
                try:
                    layer_written = extract_archive(blob_path, dest_path)
                except ArchiveExtractionError as error:
                    module.warn(
                        "{error}; placing the downloaded file as-is "
                        "instead".format(error=error)
                    )
                    layer_written = place_file(
                        blob_path,
                        dest_path,
                        layer["filename"],
                    )
            else:
                layer_written = place_file(
                    blob_path,
                    dest_path,
                    layer["filename"],
                )
            written_paths.update(layer_written)

        # Apply ownership/permissions to written paths
        apply_ownership_permissions(
            written_paths,
            owner=module.params["owner"],
            group=module.params["group"],
            mode=module.params["mode"],
        )

        # Write marker file for idempotency
        write_marker(
            dest_path,
            composite_digest,
            parsed_layers,
            module.params["reference"],
            module.params["owner"],
            module.params["group"],
            module.params["mode"],
        )

        # Clean up downloaded blob temp files before returning
        for _, blob_path in downloaded_layers:
            if os.path.exists(blob_path):
                os.unlink(blob_path)

        changed = True
        module.exit_json(
            changed=changed,
            msg="artefact deployed"
        )

    except (
        HTTPError,
        URLError,
        ValueError,
        JSONDecodeError,
        OSError,
    ) as error:
        for _, blob_path in downloaded_layers:
            if os.path.exists(blob_path):
                os.unlink(blob_path)
        if isinstance(error, HTTPError):
            module.fail_json(msg=describe_http_error(error))
        else:
            module.fail_json(msg=str(error))


def main():
    run_module()


if __name__ == "__main__":
    main()
