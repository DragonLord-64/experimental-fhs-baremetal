import io
from email.message import Message
import grp
import hashlib
import json
import importlib.util
import os
import pwd
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import unittest
from urllib.error import HTTPError
from unittest.mock import MagicMock, patch
from pathlib import Path

LIBRARY_DIR = Path(__file__).resolve().parent
MODULE_PATH = (LIBRARY_DIR / "raw_artefact.py").resolve()
SPEC = importlib.util.spec_from_file_location("raw_artefact", MODULE_PATH)
raw_artefact = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(raw_artefact)


class ModuleFailed(Exception):
    def __init__(self, payload):
        super().__init__(payload["msg"])
        self.payload = payload


def run_module(params):
    payload = json.dumps({"ANSIBLE_MODULE_ARGS": params})
    result = subprocess.run(
        [sys.executable, str(MODULE_PATH)],
        input=payload,
        capture_output=True,
        text=True,
        check=False,
    )
    stdout = result.stdout.strip()
    data = json.loads(stdout) if stdout else {}
    return result, data


def unlink_if_exists(path):
    if os.path.exists(path):
        os.unlink(path)


def make_tar_blob(path, members, mode="w:gz"):
    with tarfile.open(path, mode=mode) as tar_obj:
        for name, data in members.items():
            tar_info = tarfile.TarInfo(name=name)
            tar_info.size = len(data)
            tar_obj.addfile(tar_info, io.BytesIO(data))


def make_tar_with_directory(path, mode="w:gz"):
    with tarfile.open(path, mode=mode) as tar_obj:
        directory = tarfile.TarInfo(name="nested")
        directory.type = tarfile.DIRTYPE
        tar_obj.addfile(directory)

        nested_file = tarfile.TarInfo(name="nested/config.txt")
        nested_file.size = len(b"nested-data")
        tar_obj.addfile(nested_file, io.BytesIO(b"nested-data"))

        root_file = tarfile.TarInfo(name="root.txt")
        root_file.size = len(b"root-data")
        tar_obj.addfile(root_file, io.BytesIO(b"root-data"))


def add_tar_member(tar_obj, name, data=b"", member_type=tarfile.REGTYPE,
                   linkname=""):
    tar_info = tarfile.TarInfo(name=name)
    tar_info.type = member_type
    tar_info.linkname = linkname
    tar_info.size = len(data) if member_type == tarfile.REGTYPE else 0
    fileobj = io.BytesIO(data) if member_type == tarfile.REGTYPE else None
    tar_obj.addfile(tar_info, fileobj)


class RawArtefactModuleTest(unittest.TestCase):
    def test_parse_www_authenticate_parses_spec_example(self):
        header = (
            'Bearer realm="https://auth.example.com/token",'
            'service="registry.example.com",'
            'scope="repository:myorg/myapp:pull"'
        )

        self.assertEqual(
            raw_artefact.parse_www_authenticate(header),
            {
                "realm": "https://auth.example.com/token",
                "service": "registry.example.com",
                "scope": "repository:myorg/myapp:pull",
            },
        )

    def test_parse_www_authenticate_handles_whitespace_and_missing_scope(self):
        header = (
            "  Bearer   realm = https://auth.example.com/token  , "
            ' service = "registry.example.com"  '
        )

        self.assertEqual(
            raw_artefact.parse_www_authenticate(header),
            {
                "realm": "https://auth.example.com/token",
                "service": "registry.example.com",
            },
        )

    def test_parse_www_authenticate_requires_realm(self):
        with self.assertRaisesRegex(
            ValueError,
            "missing realm",
        ):
            raw_artefact.parse_www_authenticate(
                'Bearer service="registry.example.com"'
            )

    def test_parse_www_authenticate_requires_bearer_scheme(self):
        with self.assertRaisesRegex(
            ValueError,
            "must be Bearer",
        ):
            raw_artefact.parse_www_authenticate(
                'Basic realm="https://auth.example.com/token"'
            )

    def test_describe_http_error_includes_url_and_response_body(self):
        body = b'{"errors":[{"code":"DENIED","message":"denied"}]}'
        error = HTTPError(
            url="https://registry.example.com/v2/myorg/app/manifests/v1",
            code=400,
            msg="Bad Request",
            hdrs=Message(),
            fp=io.BytesIO(body),
        )
        self.addCleanup(error.close)

        described = raw_artefact.describe_http_error(error)

        self.assertIn("400", described)
        self.assertIn(
            "https://registry.example.com/v2/myorg/app/manifests/v1",
            described,
        )
        self.assertIn("DENIED", described)
        self.assertIn("denied", described)

    def test_describe_http_error_handles_empty_body(self):
        error = HTTPError(
            url="https://registry.example.com/v2/myorg/app/manifests/v1",
            code=400,
            msg="Bad Request",
            hdrs=Message(),
            fp=io.BytesIO(b""),
        )
        self.addCleanup(error.close)

        described = raw_artefact.describe_http_error(error)

        self.assertIn("400", described)
        self.assertIn("Bad Request", described)

    def test_redirect_handler_strips_auth_on_cross_host_redirect(self):
        handler = raw_artefact.CrossHostSafeRedirectHandler()
        original = urllib.request.Request(
            "https://registry.example.com/v2/myorg/app/blobs/sha256:abc",
            headers={"Authorization": "Bearer secret-token"},
        )

        redirected = handler.redirect_request(
            original,
            fp=None,
            code=307,
            msg="Temporary Redirect",
            headers=Message(),
            newurl=(
                "https://s3.amazonaws.com/bucket/blobs/abc"
                "?X-Amz-Signature=presigned"
            ),
        )

        self.assertNotIn("Authorization", redirected.headers)

    def test_redirect_handler_keeps_authorization_on_same_host_redirect(self):
        handler = raw_artefact.CrossHostSafeRedirectHandler()
        original = urllib.request.Request(
            "https://registry.example.com/v2/myorg/app/blobs/sha256:abc",
            headers={"Authorization": "Bearer secret-token"},
        )

        redirected = handler.redirect_request(
            original,
            fp=None,
            code=307,
            msg="Temporary Redirect",
            headers=Message(),
            newurl="https://registry.example.com/v2/myorg/app/blobs/other",
        )

        self.assertEqual(
            redirected.headers["Authorization"], "Bearer secret-token"
        )

    def test_build_opener_honors_no_proxy(self):
        opener = raw_artefact.build_opener(
            https_proxy="http://proxy.example.com:3128",
            no_proxy="skip.example.com,.internal.example.com",
        )
        proxy_handler = next(
            handler
            for handler in opener.handlers
            if isinstance(handler, urllib.request.ProxyHandler)
        )

        bypass_request = urllib.request.Request(
            "https://skip.example.com/v2/test"
        )
        proxy_handler.https_open(bypass_request)
        self.assertEqual(bypass_request.host, "skip.example.com")

        internal_request = urllib.request.Request(
            "https://node.internal.example.com/v2/test"
        )
        proxy_handler.https_open(internal_request)
        self.assertEqual(internal_request.host, "node.internal.example.com")

        proxied_request = urllib.request.Request(
            "https://use.example.com/v2/test"
        )
        proxy_handler.https_open(proxied_request)
        self.assertEqual(proxied_request.host, "proxy.example.com:3128")

    def test_parse_layers_returns_manifest_order(self):
        manifest = {
            "layers": [
                {
                    "digest": "sha256:first",
                    "size": 11,
                    "annotations": {
                        "org.opencontainers.image.title": "config.tar.gz",
                    },
                },
                {
                    "digest": "sha256:second",
                    "size": 7,
                    "annotations": {
                        "org.opencontainers.image.title": "binary.txt",
                    },
                },
            ]
        }

        self.assertEqual(
            raw_artefact.parse_layers(manifest),
            [
                {
                    "filename": "config.tar.gz",
                    "digest": "sha256:first",
                    "size": 11,
                },
                {
                    "filename": "binary.txt",
                    "digest": "sha256:second",
                    "size": 7,
                },
            ],
        )

    def test_parse_layers_requires_title_annotation(self):
        manifest = {
            "layers": [
                {
                    "digest": "sha256:missing",
                    "size": 11,
                    "annotations": {},
                }
            ]
        }

        with self.assertRaisesRegex(
            ValueError,
            r"layer 0 \(sha256:missing\) is missing "
            r"annotations\.org\.opencontainers\.image\.title",
        ):
            raw_artefact.parse_layers(manifest)

    def test_parse_layers_requires_non_empty_layers(self):
        for manifest in ({}, {"layers": []}):
            with self.subTest(manifest=manifest):
                with self.assertRaisesRegex(
                    ValueError,
                    "manifest must contain at least one layer",
                ):
                    raw_artefact.parse_layers(manifest)

    def test_fetch_manifest_uses_expected_url_and_accept_header(self):
        response = MagicMock()
        response.read.return_value = json.dumps(
            {"layers": [1]}
        ).encode("utf-8")
        opener = MagicMock()
        opener.open.return_value.__enter__.return_value = response

        manifest = raw_artefact.fetch_manifest(
            opener=opener,
            host="mirror.example.com:5000",
            repository="myorg/myartefact",
            reference="v1.2.3",
            timeout=42,
            username=None,
            password=None,
        )

        self.assertEqual(manifest, {"layers": [1]})
        request = opener.open.call_args.args[0]
        self.assertEqual(
            request.full_url,
            "https://mirror.example.com:5000/v2/myorg/myartefact/manifests/"
            "v1.2.3",
        )
        self.assertEqual(
            request.headers["Accept"],
            raw_artefact.MANIFEST_ACCEPT,
        )
        self.assertEqual(opener.open.call_args.kwargs["timeout"], 42)

    def test_fetch_manifest_retries_with_bearer_token_after_401(self):
        headers = Message()
        headers["WWW-Authenticate"] = (
            'Bearer realm="https://auth.example.com/token", '
            'service="registry.example.com", '
            'scope="repository:myorg/myapp:pull"'
        )
        initial_error = HTTPError(
            url="https://registry.example.com/v2/myorg/myapp/manifests/v1.2.3",
            code=401,
            msg="Unauthorized",
            hdrs=headers,
            fp=io.BytesIO(b""),
        )
        self.addCleanup(initial_error.close)

        token_response = MagicMock()
        token_response.read.return_value = json.dumps(
            {"token": "abc123"}
        ).encode("utf-8")
        token_context = MagicMock()
        token_context.__enter__.return_value = token_response

        manifest_response = MagicMock()
        manifest_response.read.return_value = json.dumps(
            {
                "layers": [
                    {"digest": "sha256:first", "size": 1, "annotations": {}}
                ]
            }
        ).encode("utf-8")
        manifest_context = MagicMock()
        manifest_context.__enter__.return_value = manifest_response

        opener = MagicMock()
        opener.open.side_effect = [
            initial_error,
            token_context,
            manifest_context,
        ]

        manifest = raw_artefact.fetch_manifest(
            opener=opener,
            host="registry.example.com",
            repository="myorg/myapp",
            reference="v1.2.3",
            timeout=30,
            username="robot",
            password="secret",
        )

        self.assertEqual(
            manifest,
            {
                "layers": [
                    {"digest": "sha256:first", "size": 1, "annotations": {}}
                ]
            },
        )
        self.assertEqual(opener.open.call_count, 3)

        token_request = opener.open.call_args_list[1].args[0]
        self.assertEqual(
            token_request.full_url,
            "https://auth.example.com/token?service=registry.example.com&"
            "scope=repository%3Amyorg%2Fmyapp%3Apull",
        )
        self.assertEqual(
            token_request.headers["Authorization"],
            "Basic cm9ib3Q6c2VjcmV0",
        )

        retry_request = opener.open.call_args_list[2].args[0]
        self.assertEqual(
            retry_request.headers["Authorization"],
            "Bearer abc123",
        )
        self.assertEqual(
            retry_request.headers["Accept"],
            raw_artefact.MANIFEST_ACCEPT,
        )

    def test_download_blob_returns_temp_file_for_matching_digest(self):
        blob = b"hello world"
        digest = "sha256:{digest}".format(
            digest=hashlib.sha256(blob).hexdigest()
        )
        response = MagicMock()
        response.read.side_effect = [blob[:5], blob[5:], b""]
        context = MagicMock()
        context.__enter__.return_value = response
        opener = MagicMock()
        opener.open.return_value = context

        blob_path = raw_artefact.download_blob(
            opener=opener,
            host="registry.example.com",
            repository="myorg/myapp",
            digest=digest,
            timeout=30,
            username=None,
            password=None,
        )
        self.addCleanup(unlink_if_exists, blob_path)

        self.assertTrue(os.path.exists(blob_path))
        with open(blob_path, "rb") as blob_file:
            self.assertEqual(blob_file.read(), blob)

    def test_download_blob_rejects_tampered_content(self):
        blob = b"tampered"
        digest = "sha256:{digest}".format(
            digest=hashlib.sha256(b"expected").hexdigest()
        )
        response = MagicMock()
        response.read.side_effect = [blob, b""]
        context = MagicMock()
        context.__enter__.return_value = response
        opener = MagicMock()
        opener.open.return_value = context
        temp_paths = []

        original_named_temporary_file = (
            raw_artefact.tempfile.NamedTemporaryFile
        )

        def tracking_named_temporary_file(*args, **kwargs):
            temp_file = original_named_temporary_file(*args, **kwargs)
            temp_paths.append(temp_file.name)
            return temp_file

        with patch.object(
            raw_artefact.tempfile,
            "NamedTemporaryFile",
            side_effect=tracking_named_temporary_file,
        ):
            with self.assertRaisesRegex(
                ValueError,
                "digest mismatch for blob",
            ):
                raw_artefact.download_blob(
                    opener=opener,
                    host="registry.example.com",
                    repository="myorg/myapp",
                    digest=digest,
                    timeout=30,
                    username=None,
                    password=None,
                )

        self.assertEqual(len(temp_paths), 1)
        self.assertFalse(os.path.exists(temp_paths[0]))

    def test_extract_archive_extracts_gzip_tar(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            blob_path = os.path.join(temp_dir, "archive.tar.gz")
            dest_path = os.path.join(temp_dir, "dest")
            os.mkdir(dest_path)

            make_tar_with_directory(blob_path)

            raw_artefact.extract_archive(blob_path, dest_path)

            with open(os.path.join(dest_path, "root.txt"), "rb") as root_file:
                self.assertEqual(root_file.read(), b"root-data")
            with open(
                os.path.join(dest_path, "nested", "config.txt"),
                "rb",
            ) as nested_file:
                self.assertEqual(nested_file.read(), b"nested-data")

    def test_extract_archive_falls_back_to_plain_tar(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            blob_path = os.path.join(temp_dir, "archive.tar.gz")
            dest_path = os.path.join(temp_dir, "dest")
            os.mkdir(dest_path)

            make_tar_blob(
                blob_path,
                {"fallback.txt": b"plain-tar"},
                mode="w:",
            )

            raw_artefact.extract_archive(blob_path, dest_path)

            with open(
                os.path.join(dest_path, "fallback.txt"),
                "rb",
            ) as extracted_file:
                self.assertEqual(extracted_file.read(), b"plain-tar")

    def test_extract_archive_raises_on_unsupported_compression(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            blob_path = os.path.join(temp_dir, "archive.tar.gz")
            dest_path = os.path.join(temp_dir, "dest")
            os.mkdir(dest_path)

            with open(blob_path, "wb") as blob_file:
                blob_file.write(b"not a tar or gzip file at all")

            with self.assertRaises(raw_artefact.ArchiveExtractionError):
                raw_artefact.extract_archive(blob_path, dest_path)

    def test_safe_tar_extract_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            blob_path = os.path.join(temp_dir, "malicious.tar.gz")
            dest_path = os.path.join(temp_dir, "dest")
            os.mkdir(dest_path)

            with tarfile.open(blob_path, mode="w:gz") as tar_obj:
                add_tar_member(tar_obj, "safe.txt", b"safe")
                add_tar_member(
                    tar_obj,
                    "../../../etc/passwd",
                    b"bad",
                )

            with self.assertRaisesRegex(
                ValueError,
                "path traversal detected",
            ):
                raw_artefact.extract_archive(blob_path, dest_path)

            self.assertEqual(os.listdir(dest_path), [])
            self.assertFalse(
                os.path.exists(os.path.join(dest_path, "safe.txt"))
            )

    def test_safe_tar_extract_rejects_escaping_hardlink(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            blob_path = os.path.join(temp_dir, "malicious-hardlink.tar.gz")
            dest_path = os.path.join(temp_dir, "dest")
            os.mkdir(dest_path)

            with tarfile.open(blob_path, mode="w:gz") as tar_obj:
                add_tar_member(tar_obj, "safe.txt", b"safe")
                add_tar_member(
                    tar_obj,
                    "dir/link",
                    member_type=tarfile.LNKTYPE,
                    linkname="../outside",
                )

            with self.assertRaisesRegex(
                ValueError,
                "path traversal detected",
            ):
                raw_artefact.extract_archive(blob_path, dest_path)

            self.assertEqual(os.listdir(dest_path), [])

    def test_safe_tar_extract_treats_absolute_member_as_relative(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            blob_path = os.path.join(temp_dir, "absolute-paths.tar.gz")
            dest_path = os.path.join(temp_dir, "dest")
            os.mkdir(dest_path)

            with tarfile.open(blob_path, mode="w:gz") as tar_obj:
                add_tar_member(
                    tar_obj,
                    "/home/root/tango/bin/sim/tool",
                    b"binary-data",
                )

            raw_artefact.extract_archive(blob_path, dest_path)

            extracted_path = os.path.join(
                dest_path, "home", "root", "tango", "bin", "sim", "tool"
            )
            self.assertTrue(os.path.exists(extracted_path))
            with open(extracted_path, "rb") as extracted_file:
                self.assertEqual(extracted_file.read(), b"binary-data")

    def test_safe_tar_extract_resolves_absolute_symlink_under_dest(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            blob_path = os.path.join(temp_dir, "absolute-symlink.tar.gz")
            dest_path = os.path.join(temp_dir, "dest")
            os.mkdir(dest_path)

            with tarfile.open(blob_path, mode="w:gz") as tar_obj:
                add_tar_member(
                    tar_obj,
                    "root/tango/bin/sim/hcc/tool",
                    b"real-binary",
                )
                add_tar_member(
                    tar_obj,
                    "bin/sim/hcc/tool",
                    member_type=tarfile.SYMTYPE,
                    linkname="/root/tango/bin/sim/hcc/tool",
                )

            raw_artefact.extract_archive(blob_path, dest_path)

            link_path = os.path.join(dest_path, "bin", "sim", "hcc", "tool")
            self.assertTrue(os.path.islink(link_path))
            resolved = os.path.realpath(link_path)
            self.assertTrue(resolved.startswith(os.path.realpath(dest_path)))
            with open(link_path, "rb") as linked_file:
                self.assertEqual(linked_file.read(), b"real-binary")

    def test_safe_tar_extract_resolves_absolute_hardlink_under_dest(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            blob_path = os.path.join(temp_dir, "absolute-hardlink.tar.gz")
            dest_path = os.path.join(temp_dir, "dest")
            os.mkdir(dest_path)

            with tarfile.open(blob_path, mode="w:gz") as tar_obj:
                add_tar_member(
                    tar_obj,
                    "root/tango/bin/spf1/Spf1",
                    b"real-binary",
                )
                add_tar_member(
                    tar_obj,
                    "bin/spf1/Spf1",
                    member_type=tarfile.LNKTYPE,
                    linkname="/root/tango/bin/spf1/Spf1",
                )

            raw_artefact.extract_archive(blob_path, dest_path)

            link_path = os.path.join(dest_path, "bin", "spf1", "Spf1")
            with open(link_path, "rb") as linked_file:
                self.assertEqual(linked_file.read(), b"real-binary")

    def test_safe_tar_extract_rejects_disguised_absolute_traversal(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            blob_path = os.path.join(temp_dir, "disguised.tar.gz")
            dest_path = os.path.join(temp_dir, "dest")
            os.mkdir(dest_path)

            with tarfile.open(blob_path, mode="w:gz") as tar_obj:
                add_tar_member(tar_obj, "/../../../etc/passwd", b"bad")

            with self.assertRaisesRegex(
                ValueError,
                "path traversal detected",
            ):
                raw_artefact.extract_archive(blob_path, dest_path)

            self.assertEqual(os.listdir(dest_path), [])

    def test_place_file_copies_blob_bytes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            blob_path = os.path.join(temp_dir, "blob.bin")
            dest_path = os.path.join(temp_dir, "dest")
            os.mkdir(dest_path)
            payload = b'{"answer":42}\n'

            with open(blob_path, "wb") as blob_file:
                blob_file.write(payload)

            raw_artefact.place_file(blob_path, dest_path, "config.json")

            with open(
                os.path.join(dest_path, "config.json"),
                "rb",
            ) as placed_file:
                self.assertEqual(placed_file.read(), payload)

    def test_place_file_rejects_traversal_filename(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            blob_path = os.path.join(temp_dir, "blob.bin")
            dest_path = os.path.join(temp_dir, "dest")
            os.mkdir(dest_path)

            with open(blob_path, "wb") as blob_file:
                blob_file.write(b"payload")

            with self.assertRaisesRegex(
                ValueError,
                "path traversal detected",
            ):
                raw_artefact.place_file(
                    blob_path,
                    dest_path,
                    "../../etc/passwd",
                )

            self.assertEqual(os.listdir(dest_path), [])

    def test_run_module_reaches_ownership_stub_with_layers(self):
        fake_module = MagicMock()
        fake_module.check_mode = False
        fake_module.params = {
            "registry": "registry.example.com",
            "repository": "myorg/myapp-config",
            "reference": "v1.2.3",
            "dest_path": "/tmp/config",
            "owner": None,
            "group": None,
            "mode": None,
            "create": False,
            "username": None,
            "password": None,
            "http_proxy": None,
            "https_proxy": None,
            "no_proxy": None,
            "registry_mirror": "cache.internal.example.com",
            "tls_verify": True,
            "timeout": 30,
        }

        def fail_json(**kwargs):
            raise ModuleFailed(kwargs)

        fake_module.fail_json.side_effect = fail_json

        manifest = {
            "layers": [
                {
                    "digest": "sha256:first",
                    "size": 11,
                    "annotations": {
                        "org.opencontainers.image.title": "config.tar.gz",
                    },
                }
            ]
        }

        with patch.object(
            raw_artefact,
            "AnsibleModule",
            return_value=fake_module,
        ), patch.object(
            raw_artefact,
            "build_opener",
            return_value="opener",
        ) as build_opener_mock, patch.object(
            raw_artefact,
            "fetch_manifest",
            return_value=manifest,
        ) as fetch_manifest_mock:
            temp_paths = []
            for _ in manifest["layers"]:
                temp_file = os.path.abspath(
                    "tempfile-{index}".format(index=len(temp_paths))
                )
                temp_paths.append(temp_file)

            with patch.object(
                raw_artefact,
                "download_blob",
                side_effect=temp_paths,
            ) as download_blob_mock:
                with patch.object(
                    raw_artefact,
                    "extract_archive",
                ) as extract_archive_mock, patch.object(
                    raw_artefact,
                    "place_file",
                ) as place_file_mock, patch.object(
                    raw_artefact.os.path,
                    "isdir",
                    return_value=True,
                ), patch.object(
                    raw_artefact.os.path,
                    "exists",
                    return_value=False,
                ), patch.object(
                    raw_artefact,
                    "write_marker",
                ):
                    raw_artefact.run_module()

        fake_module.exit_json.assert_called_once()
        call_kwargs = fake_module.exit_json.call_args.kwargs
        self.assertTrue(call_kwargs["changed"])
        build_opener_mock.assert_called_once_with(
            http_proxy=None,
            https_proxy=None,
            no_proxy=None,
        )
        fetch_manifest_mock.assert_called_once_with(
            opener="opener",
            host="cache.internal.example.com",
            repository="myorg/myapp-config",
            reference="v1.2.3",
            timeout=30,
            username=None,
            password=None,
            tls_verify=True,
        )
        download_blob_mock.assert_called_once_with(
            opener="opener",
            host="cache.internal.example.com",
            repository="myorg/myapp-config",
            digest="sha256:first",
            timeout=30,
            username=None,
            password=None,
            tls_verify=True,
        )
        extract_archive_mock.assert_called_once_with(
            temp_paths[0],
            "/tmp/config",
        )
        place_file_mock.assert_not_called()

    def test_run_module_falls_back_to_place_file_on_extraction_failure(self):
        fake_module = MagicMock()
        fake_module.check_mode = False
        fake_module.params = {
            "registry": "registry.example.com",
            "repository": "myorg/myapp-config",
            "reference": "v1.2.3",
            "dest_path": "/tmp/config",
            "owner": None,
            "group": None,
            "mode": None,
            "create": False,
            "username": None,
            "password": None,
            "http_proxy": None,
            "https_proxy": None,
            "no_proxy": None,
            "registry_mirror": "cache.internal.example.com",
            "tls_verify": True,
            "timeout": 30,
        }

        def fail_json(**kwargs):
            raise ModuleFailed(kwargs)

        fake_module.fail_json.side_effect = fail_json

        manifest = {
            "layers": [
                {
                    "digest": "sha256:first",
                    "size": 11,
                    "annotations": {
                        "org.opencontainers.image.title": "config.tar.gz",
                    },
                }
            ]
        }

        with patch.object(
            raw_artefact,
            "AnsibleModule",
            return_value=fake_module,
        ), patch.object(
            raw_artefact,
            "build_opener",
            return_value="opener",
        ), patch.object(
            raw_artefact,
            "fetch_manifest",
            return_value=manifest,
        ):
            with patch.object(
                raw_artefact,
                "download_blob",
                return_value="/tmp/downloaded-blob",
            ):
                with patch.object(
                    raw_artefact,
                    "extract_archive",
                    side_effect=raw_artefact.ArchiveExtractionError(
                        "could not unpack 'config.tar.gz' as a tar archive"
                    ),
                ) as extract_archive_mock, patch.object(
                    raw_artefact,
                    "place_file",
                    return_value=set(),
                ) as place_file_mock, patch.object(
                    raw_artefact.os.path,
                    "isdir",
                    return_value=True,
                ), patch.object(
                    raw_artefact.os.path,
                    "exists",
                    return_value=False,
                ), patch.object(
                    raw_artefact,
                    "write_marker",
                ):
                    raw_artefact.run_module()

        extract_archive_mock.assert_called_once_with(
            "/tmp/downloaded-blob",
            "/tmp/config",
        )
        place_file_mock.assert_called_once_with(
            "/tmp/downloaded-blob",
            "/tmp/config",
            "config.tar.gz",
        )
        fake_module.warn.assert_called_once()
        warning_message = fake_module.warn.call_args.args[0]
        self.assertIn("config.tar.gz", warning_message)
        fake_module.exit_json.assert_called_once()
        self.assertTrue(fake_module.exit_json.call_args.kwargs["changed"])

    def test_run_module_cleans_up_downloads_on_failure(self):
        fake_module = MagicMock()
        fake_module.check_mode = False
        fake_module.params = {
            "registry": "registry.example.com",
            "repository": "myorg/myapp-config",
            "reference": "v1.2.3",
            "dest_path": "/tmp/config",
            "owner": None,
            "group": None,
            "mode": None,
            "create": False,
            "username": None,
            "password": None,
            "http_proxy": None,
            "https_proxy": None,
            "no_proxy": None,
            "registry_mirror": None,
            "tls_verify": True,
            "timeout": 30,
        }

        def fail_json(**kwargs):
            raise ModuleFailed(kwargs)

        fake_module.fail_json.side_effect = fail_json
        manifest = {
            "layers": [
                {
                    "digest": "sha256:first",
                    "size": 11,
                    "annotations": {
                        "org.opencontainers.image.title": "config.tar.gz",
                    },
                },
                {
                    "digest": "sha256:second",
                    "size": 7,
                    "annotations": {
                        "org.opencontainers.image.title": "binary.txt",
                    },
                },
            ]
        }

        with tempfile.NamedTemporaryFile(delete=False) as first_temp:
            first_temp.write(b"ok")
            first_temp_path = first_temp.name
        self.addCleanup(unlink_if_exists, first_temp_path)
        removed_paths = []
        original_unlink = os.unlink

        def record_unlink(path):
            removed_paths.append(path)
            original_unlink(path)

        with patch.object(
            raw_artefact,
            "AnsibleModule",
            return_value=fake_module,
        ), patch.object(
            raw_artefact,
            "build_opener",
            return_value="opener",
        ), patch.object(
            raw_artefact,
            "fetch_manifest",
            return_value=manifest,
        ), patch.object(
            raw_artefact,
            "download_blob",
            side_effect=[
                first_temp_path,
                ValueError("digest mismatch for blob sha256:second"),
            ],
        ), patch.object(
            raw_artefact.os,
            "unlink",
            side_effect=record_unlink,
        ), patch.object(
            raw_artefact.os.path,
            "isdir",
            return_value=True,
        ), patch.object(
            raw_artefact,
            "load_marker",
            return_value=None,
        ):
            with self.assertRaises(ModuleFailed) as raised:
                raw_artefact.run_module()

        self.assertEqual(
            raised.exception.payload["msg"],
            "digest mismatch for blob sha256:second",
        )
        self.assertEqual(removed_paths, [first_temp_path])
        self.assertFalse(os.path.exists(first_temp_path))

    def test_run_module_cleans_up_downloads_on_oserror(self):
        fake_module = MagicMock()
        fake_module.check_mode = False
        fake_module.params = {
            "registry": "registry.example.com",
            "repository": "myorg/myapp-config",
            "reference": "v1.2.3",
            "dest_path": "/tmp/config",
            "owner": None,
            "group": None,
            "mode": None,
            "create": False,
            "username": None,
            "password": None,
            "http_proxy": None,
            "https_proxy": None,
            "no_proxy": None,
            "registry_mirror": None,
            "tls_verify": True,
            "timeout": 30,
        }

        def fail_json(**kwargs):
            raise ModuleFailed(kwargs)

        fake_module.fail_json.side_effect = fail_json
        manifest = {
            "layers": [
                {
                    "digest": "sha256:first",
                    "size": 11,
                    "annotations": {
                        "org.opencontainers.image.title": "config.tar.gz",
                    },
                },
                {
                    "digest": "sha256:second",
                    "size": 7,
                    "annotations": {
                        "org.opencontainers.image.title": "binary.txt",
                    },
                },
            ]
        }

        with tempfile.NamedTemporaryFile(delete=False) as first_temp:
            first_temp.write(b"ok")
            first_temp_path = first_temp.name
        self.addCleanup(unlink_if_exists, first_temp_path)
        removed_paths = []
        original_unlink = os.unlink

        def record_unlink(path):
            removed_paths.append(path)
            original_unlink(path)

        with patch.object(
            raw_artefact,
            "AnsibleModule",
            return_value=fake_module,
        ), patch.object(
            raw_artefact,
            "build_opener",
            return_value="opener",
        ), patch.object(
            raw_artefact,
            "fetch_manifest",
            return_value=manifest,
        ), patch.object(
            raw_artefact,
            "download_blob",
            side_effect=[first_temp_path, OSError("disk full")],
        ), patch.object(
            raw_artefact.os,
            "unlink",
            side_effect=record_unlink,
        ), patch.object(
            raw_artefact.os.path,
            "isdir",
            return_value=True,
        ), patch.object(
            raw_artefact,
            "load_marker",
            return_value=None,
        ):
            with self.assertRaises(ModuleFailed) as raised:
                raw_artefact.run_module()

        self.assertEqual(raised.exception.payload["msg"], "disk full")
        self.assertEqual(removed_paths, [first_temp_path])
        self.assertFalse(os.path.exists(first_temp_path))

    def test_missing_required_argument_fails(self):
        result, data = run_module(
            {
                "repository": "myorg/myapp-config",
                "reference": "v1.2.3",
                "dest_path": "/tmp/config",
            }
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing required arguments", data["msg"])
        self.assertIn("registry", data["msg"])

    def test_empty_reference_fails_validation(self):
        result, data = run_module(
            {
                "registry": "registry.example.com",
                "repository": "myorg/myapp-config",
                "reference": "",
                "dest_path": "/tmp/config",
            }
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(
            data["msg"],
            "reference must be a non-empty string",
        )

    def test_apply_ownership_permissions_applies_mode_to_tree(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = os.path.join(temp_dir, "test.txt")
            with open(file_path, "w") as f:
                f.write("content")

            subdir = os.path.join(temp_dir, "subdir")
            os.mkdir(subdir)
            nested_file = os.path.join(subdir, "nested.txt")
            with open(nested_file, "w") as f:
                f.write("nested")

            written_paths = {file_path, subdir, nested_file}
            raw_artefact.apply_ownership_permissions(
                written_paths,
                mode="0755",
            )

            self.assertEqual(os.stat(file_path).st_mode & 0o777, 0o755)
            self.assertEqual(os.stat(subdir).st_mode & 0o777, 0o755)
            self.assertEqual(os.stat(nested_file).st_mode & 0o777, 0o755)

    def test_apply_ownership_permissions_skips_dangling_symlink_mode(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            link_path = os.path.join(temp_dir, "dangling")
            os.symlink("/no/such/target", link_path)

            # Must not raise: a dangling symlink's target doesn't exist,
            # so chmod (which follows symlinks by default) would fail if
            # it weren't skipped for symlinks.
            raw_artefact.apply_ownership_permissions(
                {link_path},
                mode="0755",
            )

            self.assertTrue(os.path.islink(link_path))

    def test_apply_ownership_permissions_chowns_dangling_symlink_itself(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            link_path = os.path.join(temp_dir, "dangling")
            os.symlink("/no/such/target", link_path)

            current_uid = os.getuid()
            current_gid = os.getgid()

            # Must not raise, and must not follow the (missing) target --
            # os.lstat confirms the symlink itself was chowned, not an
            # attempt to chown its nonexistent target.
            raw_artefact.apply_ownership_permissions(
                {link_path},
                owner=pwd.getpwuid(current_uid).pw_name,
                group=grp.getgrgid(current_gid).gr_name,
            )

            lstat_result = os.lstat(link_path)
            self.assertEqual(lstat_result.st_uid, current_uid)
            self.assertEqual(lstat_result.st_gid, current_gid)

    def test_apply_ownership_permissions_noop_when_all_none(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = os.path.join(temp_dir, "test.txt")
            with open(file_path, "w") as f:
                f.write("content")
            original_mode = os.stat(file_path).st_mode

            written_paths = {file_path}
            raw_artefact.apply_ownership_permissions(written_paths)

            self.assertEqual(os.stat(file_path).st_mode, original_mode)

    def test_apply_ownership_permissions_only_touches_written_paths(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a pre-existing file (not in written_paths)
            preexisting_file = os.path.join(temp_dir, "preexisting.txt")
            with open(preexisting_file, "w") as f:
                f.write("preexisting")
            preexisting_mode = os.stat(preexisting_file).st_mode

            # Create a file to be modified (in written_paths)
            new_file = os.path.join(temp_dir, "new.txt")
            with open(new_file, "w") as f:
                f.write("new")

            # Apply mode only to new_file via written_paths
            written_paths = {new_file}
            raw_artefact.apply_ownership_permissions(
                written_paths,
                mode="0755",
            )

            # Verify new_file was changed
            self.assertEqual(
                os.stat(new_file).st_mode & 0o777,
                0o755,
            )
            # Verify preexisting_file was NOT changed
            self.assertEqual(
                os.stat(preexisting_file).st_mode,
                preexisting_mode,
            )

    def test_apply_ownership_permissions_rejects_invalid_mode(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = os.path.join(temp_dir, "test.txt")
            with open(file_path, "w") as f:
                f.write("content")

            written_paths = {file_path}
            with self.assertRaisesRegex(
                ValueError,
                "mode 'not-octal' is not a valid octal string",
            ):
                raw_artefact.apply_ownership_permissions(
                    written_paths,
                    mode="not-octal",
                )

    def test_apply_ownership_permissions_rejects_nonexistent_owner(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = os.path.join(temp_dir, "test.txt")
            with open(file_path, "w") as f:
                f.write("content")

            written_paths = {file_path}
            with self.assertRaisesRegex(
                ValueError,
                "owner 'nonexistent_user_xyz' does not exist",
            ):
                raw_artefact.apply_ownership_permissions(
                    written_paths,
                    owner="nonexistent_user_xyz",
                )

    def test_apply_ownership_permissions_rejects_nonexistent_group(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = os.path.join(temp_dir, "test.txt")
            with open(file_path, "w") as f:
                f.write("content")

            written_paths = {file_path}
            with self.assertRaisesRegex(
                ValueError,
                "group 'nonexistent_group_xyz' does not exist",
            ):
                raw_artefact.apply_ownership_permissions(
                    written_paths,
                    group="nonexistent_group_xyz",
                )

    def test_run_module_fails_when_dest_path_missing_and_create_false(self):
        fake_module = MagicMock()
        fake_module.params = {
            "registry": "registry.example.com",
            "repository": "myorg/myapp-config",
            "reference": "v1.2.3",
            "dest_path": "/nonexistent/path",
            "owner": None,
            "group": None,
            "mode": None,
            "create": False,
            "username": None,
            "password": None,
            "http_proxy": None,
            "https_proxy": None,
            "no_proxy": None,
            "registry_mirror": None,
            "tls_verify": True,
            "timeout": 30,
        }

        def fail_json(**kwargs):
            raise ModuleFailed(kwargs)

        fake_module.fail_json.side_effect = fail_json

        with patch.object(
            raw_artefact,
            "AnsibleModule",
            return_value=fake_module,
        ), patch.object(
            raw_artefact.os.path,
            "isdir",
            return_value=False,
        ), self.assertRaises(ModuleFailed) as raised:
            raw_artefact.run_module()

        self.assertIn(
            "dest_path '/nonexistent/path' does not exist",
            raised.exception.payload["msg"],
        )
        self.assertIn(
            "Set create to true or pre-create the path",
            raised.exception.payload["msg"],
        )

    def test_compute_composite_digest_from_sorted_layers(self):
        parsed_layers = [
            {"filename": "b.txt", "digest": "sha256:bbb", "size": 1},
            {"filename": "a.txt", "digest": "sha256:aaa", "size": 1},
            {"filename": "c.txt", "digest": "sha256:ccc", "size": 1},
        ]
        digest = raw_artefact.compute_composite_digest(parsed_layers)
        expected_sha256 = hashlib.sha256()
        for d in ["sha256:aaa", "sha256:bbb", "sha256:ccc"]:
            expected_sha256.update(d.encode("utf-8"))
        expected = "sha256:{digest}".format(
            digest=expected_sha256.hexdigest()
        )
        self.assertEqual(digest, expected)

    def test_ownership_mode_match_checks_all_attributes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "test.txt")
            with open(path, "w") as f:
                f.write("test")
            os.chmod(path, 0o755)

            self.assertTrue(
                raw_artefact.ownership_mode_match(path, None, None, "0755")
            )

            self.assertFalse(
                raw_artefact.ownership_mode_match(path, None, None, "0644")
            )

    def test_load_marker_returns_none_when_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            self.assertIsNone(raw_artefact.load_marker(temp_dir))

    def test_write_and_load_marker(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            parsed_layers = [
                {"filename": "a.tar.gz", "digest": "sha256:aaa", "size": 1},
            ]
            raw_artefact.write_marker(
                temp_dir,
                "sha256:composite",
                parsed_layers,
                "v1.2.3",
                "root",
                "wheel",
                "0755",
            )

            marker = raw_artefact.load_marker(temp_dir)
            self.assertIsNotNone(marker)
            self.assertEqual(marker["composite_digest"], "sha256:composite")
            self.assertEqual(marker["reference"], "v1.2.3")
            self.assertEqual(marker["owner"], "root")
            self.assertEqual(marker["group"], "wheel")
            self.assertEqual(marker["mode"], "0755")
            self.assertEqual(len(marker["layers"]), 1)
            self.assertEqual(marker["layers"][0]["filename"], "a.tar.gz")

    def test_run_module_creates_dest_path_when_create_true(self):
        fake_module = MagicMock()
        fake_module.check_mode = False

        with tempfile.TemporaryDirectory() as temp_dir:
            dest_path = os.path.join(temp_dir, "new_dir")

            fake_module.params = {
                "registry": "registry.example.com",
                "repository": "myorg/myapp-config",
                "reference": "v1.2.3",
                "dest_path": dest_path,
                "owner": None,
                "group": None,
                "mode": None,
                "create": True,
                "username": None,
                "password": None,
                "http_proxy": None,
                "https_proxy": None,
                "no_proxy": None,
                "registry_mirror": None,
                "tls_verify": True,
                "timeout": 30,
            }

            def fail_json(**kwargs):
                raise ModuleFailed(kwargs)

            fake_module.fail_json.side_effect = fail_json

            manifest = {
                "layers": [
                    {
                        "digest": "sha256:first",
                        "size": 11,
                        "annotations": {
                            "org.opencontainers.image.title": "config.tar.gz",
                        },
                    }
                ]
            }

            with patch.object(
                raw_artefact,
                "AnsibleModule",
                return_value=fake_module,
            ), patch.object(
                raw_artefact,
                "build_opener",
                return_value="opener",
            ), patch.object(
                raw_artefact,
                "fetch_manifest",
                return_value=manifest,
            ):
                temp_blob = os.path.join(temp_dir, "blob")
                with open(temp_blob, "wb") as f:
                    f.write(b"blob data")

                with patch.object(
                    raw_artefact,
                    "download_blob",
                    return_value=temp_blob,
                ), patch.object(
                    raw_artefact,
                    "extract_archive",
                    return_value=set(),
                ):
                    raw_artefact.run_module()

            self.assertTrue(os.path.isdir(dest_path))
            fake_module.exit_json.assert_called_once()
            call_kwargs = fake_module.exit_json.call_args.kwargs
            self.assertTrue(call_kwargs["changed"])

    def test_run_module_cleans_up_blob_files_on_success(self):
        fake_module = MagicMock()

        with tempfile.TemporaryDirectory() as temp_dir:
            dest_path = os.path.join(temp_dir, "dest")
            os.mkdir(dest_path)

            fake_module.params = {
                "registry": "registry.example.com",
                "repository": "myorg/myapp-config",
                "reference": "v1.2.3",
                "dest_path": dest_path,
                "owner": None,
                "group": None,
                "mode": None,
                "create": False,
                "username": None,
                "password": None,
                "http_proxy": None,
                "https_proxy": None,
                "no_proxy": None,
                "registry_mirror": None,
                "tls_verify": True,
                "timeout": 30,
            }

            fake_module.check_mode = False

            manifest = {
                "layers": [
                    {
                        "digest": "sha256:first",
                        "size": 11,
                        "annotations": {
                            "org.opencontainers.image.title": "config.txt",
                        },
                    },
                    {
                        "digest": "sha256:second",
                        "size": 7,
                        "annotations": {
                            "org.opencontainers.image.title": "data.txt",
                        },
                    }
                ]
            }

            with tempfile.NamedTemporaryFile(delete=False) as blob1:
                blob1.write(b"blob1 data")
                blob1_path = blob1.name
            self.addCleanup(unlink_if_exists, blob1_path)

            with tempfile.NamedTemporaryFile(delete=False) as blob2:
                blob2.write(b"blob2 data")
                blob2_path = blob2.name
            self.addCleanup(unlink_if_exists, blob2_path)

            with patch.object(
                raw_artefact,
                "AnsibleModule",
                return_value=fake_module,
            ), patch.object(
                raw_artefact,
                "build_opener",
                return_value="opener",
            ), patch.object(
                raw_artefact,
                "fetch_manifest",
                return_value=manifest,
            ), patch.object(
                raw_artefact,
                "download_blob",
                side_effect=[blob1_path, blob2_path],
            ), patch.object(
                raw_artefact,
                "place_file",
                return_value=set(),
            ), patch.object(
                raw_artefact,
                "write_marker",
            ):
                raw_artefact.run_module()

            # Verify both blob temp files were cleaned up
            self.assertFalse(os.path.exists(blob1_path))
            self.assertFalse(os.path.exists(blob2_path))
            fake_module.exit_json.assert_called_once()

    def test_run_module_first_run_creates_marker_changed_true(self):
        fake_module = MagicMock()

        with tempfile.TemporaryDirectory() as temp_dir:
            dest_path = os.path.join(temp_dir, "dest")
            os.mkdir(dest_path)

            fake_module.params = {
                "registry": "registry.example.com",
                "repository": "myorg/myapp-config",
                "reference": "v1.2.3",
                "dest_path": dest_path,
                "owner": None,
                "group": None,
                "mode": None,
                "create": False,
                "username": None,
                "password": None,
                "http_proxy": None,
                "https_proxy": None,
                "no_proxy": None,
                "registry_mirror": None,
                "tls_verify": True,
                "timeout": 30,
                "check_mode": False,
            }

            fake_module.check_mode = False

            manifest = {
                "layers": [
                    {
                        "digest": "sha256:first",
                        "size": 11,
                        "annotations": {
                            "org.opencontainers.image.title": "config.txt",
                        },
                    }
                ]
            }

            with patch.object(
                raw_artefact,
                "AnsibleModule",
                return_value=fake_module,
            ), patch.object(
                raw_artefact,
                "build_opener",
                return_value="opener",
            ), patch.object(
                raw_artefact,
                "fetch_manifest",
                return_value=manifest,
            ):
                temp_blob = os.path.join(temp_dir, "blob")
                with open(temp_blob, "wb") as f:
                    f.write(b"blob data")

                with patch.object(
                    raw_artefact,
                    "download_blob",
                    return_value=temp_blob,
                ), patch.object(
                    raw_artefact,
                    "place_file",
                    return_value=set(),
                ):
                    raw_artefact.run_module()

            fake_module.exit_json.assert_called_once()
            call_kwargs = fake_module.exit_json.call_args.kwargs
            self.assertTrue(call_kwargs["changed"])
            marker_path = os.path.join(
                dest_path,
                ".raw_artefact_state.json"
            )
            self.assertTrue(os.path.exists(marker_path))

    def test_run_module_idempotent_second_run_skips_download(self):
        fake_module = MagicMock()

        with tempfile.TemporaryDirectory() as temp_dir:
            dest_path = os.path.join(temp_dir, "dest")
            os.mkdir(dest_path)

            fake_module.params = {
                "registry": "registry.example.com",
                "repository": "myorg/myapp-config",
                "reference": "v1.2.3",
                "dest_path": dest_path,
                "owner": None,
                "group": None,
                "mode": None,
                "create": False,
                "username": None,
                "password": None,
                "http_proxy": None,
                "https_proxy": None,
                "no_proxy": None,
                "registry_mirror": None,
                "tls_verify": True,
                "timeout": 30,
                "check_mode": False,
            }

            fake_module.check_mode = False

            manifest = {
                "layers": [
                    {
                        "digest": "sha256:first",
                        "size": 11,
                        "annotations": {
                            "org.opencontainers.image.title": "config.txt",
                        },
                    }
                ]
            }

            # Pre-write marker with matching digest
            parsed_layers = [
                {"filename": "config.txt", "digest": "sha256:first",
                 "size": 11}
            ]
            composite = raw_artefact.compute_composite_digest(
                parsed_layers
            )
            raw_artefact.write_marker(
                dest_path,
                composite,
                parsed_layers,
                "v1.2.3",
                None,
                None,
                None,
            )

            with patch.object(
                raw_artefact,
                "AnsibleModule",
                return_value=fake_module,
            ), patch.object(
                raw_artefact,
                "build_opener",
                return_value="opener",
            ), patch.object(
                raw_artefact,
                "fetch_manifest",
                return_value=manifest,
            ), patch.object(
                raw_artefact,
                "download_blob",
            ) as download_mock:
                raw_artefact.run_module()

            # Verify exit_json was called with changed=False
            fake_module.exit_json.assert_called_once()
            call_kwargs = fake_module.exit_json.call_args.kwargs
            self.assertFalse(call_kwargs["changed"])

            # Verify no downloads happened
            download_mock.assert_not_called()

    def test_run_module_stale_marker_reruns_and_updates(self):
        fake_module = MagicMock()

        with tempfile.TemporaryDirectory() as temp_dir:
            dest_path = os.path.join(temp_dir, "dest")
            os.mkdir(dest_path)

            fake_module.params = {
                "registry": "registry.example.com",
                "repository": "myorg/myapp-config",
                "reference": "v1.2.3",
                "dest_path": dest_path,
                "owner": None,
                "group": None,
                "mode": None,
                "create": False,
                "username": None,
                "password": None,
                "http_proxy": None,
                "https_proxy": None,
                "no_proxy": None,
                "registry_mirror": None,
                "tls_verify": True,
                "timeout": 30,
                "check_mode": False,
            }

            fake_module.check_mode = False

            # New manifest with different digest
            manifest = {
                "layers": [
                    {
                        "digest": "sha256:new_digest",
                        "size": 11,
                        "annotations": {
                            "org.opencontainers.image.title": "config.txt",
                        },
                    }
                ]
            }

            # Pre-write marker with OLD digest
            old_parsed_layers = [
                {"filename": "config.txt", "digest": "sha256:old", "size": 11}
            ]
            old_composite = raw_artefact.compute_composite_digest(
                old_parsed_layers
            )
            raw_artefact.write_marker(
                dest_path,
                old_composite,
                old_parsed_layers,
                "v1.0.0",
                None,
                None,
                None,
            )

            with patch.object(
                raw_artefact,
                "AnsibleModule",
                return_value=fake_module,
            ), patch.object(
                raw_artefact,
                "build_opener",
                return_value="opener",
            ), patch.object(
                raw_artefact,
                "fetch_manifest",
                return_value=manifest,
            ):
                temp_blob = os.path.join(temp_dir, "blob")
                with open(temp_blob, "wb") as f:
                    f.write(b"blob data")

                with patch.object(
                    raw_artefact,
                    "download_blob",
                    return_value=temp_blob,
                ), patch.object(
                    raw_artefact,
                    "place_file",
                    return_value=set(),
                ):
                    raw_artefact.run_module()

            # Verify it proceeded (changed=True)
            fake_module.exit_json.assert_called_once()
            call_kwargs = fake_module.exit_json.call_args.kwargs
            self.assertTrue(call_kwargs["changed"])

            # Verify marker was updated
            marker = raw_artefact.load_marker(dest_path)
            self.assertEqual(
                marker["composite_digest"],
                raw_artefact.compute_composite_digest(manifest["layers"])
            )

    def test_run_module_check_mode_create_true_missing_dest_path(self):
        fake_module = MagicMock()

        with tempfile.TemporaryDirectory() as temp_dir:
            dest_path = os.path.join(temp_dir, "nonexistent", "dest")
            # dest_path does NOT exist

            fake_module.params = {
                "registry": "registry.example.com",
                "repository": "myorg/myapp-config",
                "reference": "v1.2.3",
                "dest_path": dest_path,
                "owner": None,
                "group": None,
                "mode": None,
                "create": True,  # Would normally create
                "username": None,
                "password": None,
                "http_proxy": None,
                "https_proxy": None,
                "no_proxy": None,
                "registry_mirror": None,
                "tls_verify": True,
                "timeout": 30,
                "check_mode": True,
            }

            fake_module.check_mode = True

            manifest = {
                "layers": [
                    {
                        "digest": "sha256:first",
                        "size": 11,
                        "annotations": {
                            "org.opencontainers.image.title": "config.txt",
                        },
                    }
                ]
            }

            with patch.object(
                raw_artefact,
                "AnsibleModule",
                return_value=fake_module,
            ), patch.object(
                raw_artefact,
                "build_opener",
                return_value="opener",
            ), patch.object(
                raw_artefact,
                "fetch_manifest",
                return_value=manifest,
            ), patch.object(
                raw_artefact,
                "download_blob",
            ) as download_mock:
                raw_artefact.run_module()

            # Verify exit_json was called with changed=True
            fake_module.exit_json.assert_called_once()
            call_kwargs = fake_module.exit_json.call_args.kwargs
            self.assertTrue(call_kwargs["changed"])

            # Verify directory was NOT actually created
            self.assertFalse(os.path.exists(dest_path))

            # Verify no downloads happened
            download_mock.assert_not_called()

    def test_run_module_check_mode_no_downloads_no_writes(self):
        fake_module = MagicMock()

        with tempfile.TemporaryDirectory() as temp_dir:
            dest_path = os.path.join(temp_dir, "dest")
            os.mkdir(dest_path)

            fake_module.params = {
                "registry": "registry.example.com",
                "repository": "myorg/myapp-config",
                "reference": "v1.2.3",
                "dest_path": dest_path,
                "owner": None,
                "group": None,
                "mode": None,
                "create": False,
                "username": None,
                "password": None,
                "http_proxy": None,
                "https_proxy": None,
                "no_proxy": None,
                "registry_mirror": None,
                "tls_verify": True,
                "timeout": 30,
                "check_mode": True,
            }

            fake_module.check_mode = True

            manifest = {
                "layers": [
                    {
                        "digest": "sha256:first",
                        "size": 11,
                        "annotations": {
                            "org.opencontainers.image.title": "config.txt",
                        },
                    }
                ]
            }

            with patch.object(
                raw_artefact,
                "AnsibleModule",
                return_value=fake_module,
            ), patch.object(
                raw_artefact,
                "build_opener",
                return_value="opener",
            ), patch.object(
                raw_artefact,
                "fetch_manifest",
                return_value=manifest,
            ), patch.object(
                raw_artefact,
                "download_blob",
            ) as download_mock:
                raw_artefact.run_module()

            # Verify exit_json was called with changed=True (would deploy)
            fake_module.exit_json.assert_called_once()
            call_kwargs = fake_module.exit_json.call_args.kwargs
            self.assertTrue(call_kwargs["changed"])

            # Verify no downloads happened
            download_mock.assert_not_called()

            # Verify no marker was written
            marker_path = os.path.join(
                dest_path,
                ".raw_artefact_state.json"
            )
            self.assertFalse(os.path.exists(marker_path))

    def test_build_manifest_request_uses_https_by_default(self):
        request = raw_artefact.build_manifest_request(
            host="example.com",
            repository="myorg/myapp",
            reference="v1.0.0"
        )
        self.assertTrue(request.full_url.startswith("https://"))

    def test_build_manifest_request_uses_http_when_tls_verify_false(self):
        request = raw_artefact.build_manifest_request(
            host="example.com",
            repository="myorg/myapp",
            reference="v1.0.0",
            tls_verify=False
        )
        self.assertTrue(request.full_url.startswith("http://"))

    def test_build_blob_request_uses_https_by_default(self):
        request = raw_artefact.build_blob_request(
            host="example.com",
            repository="myorg/myapp",
            digest="sha256:abc123"
        )
        self.assertTrue(request.full_url.startswith("https://"))

    def test_build_blob_request_uses_http_when_tls_verify_false(self):
        request = raw_artefact.build_blob_request(
            host="example.com",
            repository="myorg/myapp",
            digest="sha256:abc123",
            tls_verify=False
        )
        self.assertTrue(request.full_url.startswith("http://"))

    def test_open_with_bearer_auth_sends_basic_auth_on_first_request(self):
        mock_opener = MagicMock()
        mock_response = MagicMock()
        mock_opener.open.return_value.__enter__.return_value = mock_response

        mock_request = MagicMock()
        mock_request.full_url = "http://example.com/v2/test/manifests/v1.0.0"
        mock_request.data = None
        mock_request.header_items.return_value = []
        mock_request.get_method.return_value = "GET"

        raw_artefact.open_with_bearer_auth(
            opener=mock_opener,
            request=mock_request,
            timeout=10,
            username="testuser",
            password="testpass"
        )

        # Verify opener.open was called once (request with Basic auth)
        self.assertEqual(mock_opener.open.call_count, 1)

        # Get the request object passed to opener.open
        first_call_request = mock_opener.open.call_args_list[0][0][0]

        # Verify Authorization header is present and contains Basic auth
        headers = dict(first_call_request.header_items())
        self.assertIn("Authorization", headers)
        self.assertTrue(headers["Authorization"].startswith("Basic "))

    def test_open_with_bearer_auth_no_basic_auth_without_credentials(self):
        mock_opener = MagicMock()
        mock_response = MagicMock()
        mock_opener.open.return_value.__enter__.return_value = mock_response

        mock_request = MagicMock()
        mock_request.full_url = "http://example.com/v2/test/manifests/v1.0.0"
        mock_request.data = None
        mock_request.header_items.return_value = []
        mock_request.get_method.return_value = "GET"

        raw_artefact.open_with_bearer_auth(
            opener=mock_opener,
            request=mock_request,
            timeout=10,
            username=None,
            password=None
        )

        # Verify opener.open was called once
        self.assertEqual(mock_opener.open.call_count, 1)

        # Get the request object passed to opener.open
        first_call_request = mock_opener.open.call_args_list[0][0][0]

        # Verify the request passed is the original (no Basic auth added)
        self.assertEqual(first_call_request, mock_request)


if __name__ == "__main__":
    unittest.main()
