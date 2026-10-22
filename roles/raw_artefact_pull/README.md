# raw_artefact_pull

Pull OCI artefacts onto target hosts and unpack them at a destination path.

This role is the Ansible entry point for declaring one or more OCI artefacts in
`raw_artefacts`, fetching them from a registry, and materialising their
contents on the managed host. It is intended for distributing configuration,
data, or release artefacts through an OCI registry instead of a package
repository.

The `raw_artefact` module is functionally complete. It resolves OCI manifests,
parses the layer list, downloads and verifies blob digests, extracts or places
layers into `dest_path`, sets ownership and permissions (owner/group/mode), and
implements idempotency via marker files and check_mode support. Authentication
supports Basic auth (proactively sent on first request when username/password are
supplied for native Basic/htpasswd registries) and Bearer-token flows (with
fallback to Bearer-token on 401 challenge).

## Requirements

- **Ansible**: 2.9 or later
- **Python**: 3.6+ on managed hosts (stdlib urllib + tarfile only, no external dependencies)
- **Docker**: Required only for local Molecule testing (not needed for production deployment)

## Role Variables

### Per-Artefact Arguments

Pass a list of artefacts to pull in `raw_artefacts`. Each entry is a dict with the following keys:

| Argument | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `registry` | str | yes | N/A | Registry hostname, optionally including port (e.g., `registry.example.com:5000`, `docker.io`) |
| `repository` | str | yes | N/A | Repository path inside registry (e.g., `myorg/myapp`, `library/alpine`) |
| `reference` | str | yes | N/A | Tag or digest reference for the artefact (e.g., `v1.0.0`, `sha256:abc123...`) |
| `dest_path` | path | yes | N/A | Target unpack directory on the managed host. Created if `create: true` and missing |
| `create` | bool | no | `false` | If `true`, create `dest_path` if missing. If `false`, fail if `dest_path` does not exist |
| `owner` | str | no | None | Unix user for ownership (applied after unpacking). Resolves via `pwd.getpwnam()` on target |
| `group` | str | no | None | Unix group for ownership (applied after unpacking). Resolves via `grp.getgrnam()` on target |
| `mode` | str | no | None | Octal permissions for files and directories (e.g., `0755`). Applied after unpacking |
| `username` | str | no | None | Username for Basic auth to registry. Sent in initial request Authorization header |
| `password` | str | no | None | Password for Basic auth to registry. Sent in initial request Authorization header |
| `registry_mirror` | str | no | None | Mirror registry to substitute for `registry` (per-artefact override, highest precedence) |
| `http_proxy` | str | no | None | HTTP proxy URL (e.g., `http://proxy.example.com:3128`). Per-artefact override |
| `https_proxy` | str | no | None | HTTPS proxy URL. Per-artefact override |
| `no_proxy` | str | no | None | Comma-separated list of hostnames to bypass proxy. Per-artefact override |
| `tls_verify` | bool | no | `true` | If `true`, use HTTPS for registry connections. If `false`, use HTTP (for test/self-signed registries only) |
| `timeout` | int | no | 30 | HTTP request timeout in seconds |

### Role Defaults

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `raw_artefacts` | list | `[]` | List of artefact dicts to pull (each dict is a per-artefact argument set, see above) |
| `raw_artefact_http_proxy` | str | `""` | Role-level HTTP proxy (per-artefact override beats this) |
| `raw_artefact_https_proxy` | str | `""` | Role-level HTTPS proxy (per-artefact override beats this) |
| `raw_artefact_no_proxy` | str | `""` | Role-level no-proxy list (per-artefact override beats this) |
| `raw_artefact_registry_mirror` | str | `""` | Role-level registry mirror (per-artefact override beats this) |
| `raw_artefact_tls_verify` | bool | `true` | Role-level TLS verification (HTTPS by default; false = HTTP for test registries) |
| `raw_artefact_timeout` | int | 30 | Role-level HTTP request timeout in seconds |

## Usage

### Basic Example (Single Artefact)

```yaml
- hosts: all
  vars:
    raw_artefacts:
      - registry: docker.io
        repository: library/alpine
        reference: latest
        dest_path: /opt/alpine_base
        create: true
        mode: "0755"
  roles:
    - role: raw_artefact_pull
```

### Example: Registry Mirror + Credentials

```yaml
- hosts: all
  vars:
    raw_artefact_tls_verify: false  # Use HTTP for internal test registry
    raw_artefact_registry_mirror: internal-registry:5000  # Role-level mirror fallback
    raw_artefact_timeout: 60

    raw_artefacts:
      # Pull from public registry via mirror
      - registry: docker.io
        repository: myorg/app-config
        reference: v1.2.3
        dest_path: /etc/myapp
        create: true
        owner: myapp
        group: myapp
        mode: "0750"

      # Pull from private registry with credentials
      - registry: private-registry.example.com:5000
        repository: internal/secrets
        reference: main
        dest_path: /var/lib/myapp/secrets
        create: true
        username: myapp_user
        password: "{{ vault_registry_password }}"
        owner: myapp
        group: myapp
        mode: "0600"
        # Per-artefact mirror override (beats role default if broken registry)
        registry_mirror: backup-registry.example.com:5000

  roles:
    - role: raw_artefact_pull
```

### Example: Multi-Layer Artefact

```yaml
- hosts: target
  vars:
    raw_artefacts:
      - registry: registry.example.com:5000
        repository: myorg/multilayer-release
        reference: v2.0.0
        dest_path: /opt/release
        create: true
        owner: deploy
        group: deploy
        mode: "0755"
  roles:
    - role: raw_artefact_pull
```

The role will:
1. Fetch and parse the manifest
2. Download all layers
3. Extract `.tar.gz` layers to `dest_path`
4. Place plain-file layers (e.g., `.txt`, `.json`) directly in `dest_path`
5. Apply ownership and permissions to the full tree
6. Write an idempotency marker file (`.raw_artefact_state.json`)

### Precedence: Registry Substitution

Per-artefact `registry_mirror` beats role-level `raw_artefact_registry_mirror`, which beats no mirror.

Example: If per-artefact `registry: broken.invalid` but `registry_mirror: working.example.com`, the pull will succeed via `working.example.com`.

### Authentication

**Basic Auth** (e.g., htpasswd, local registries):
- Provide `username` and `password` in artefact dict
- Credentials are sent in the initial request Authorization header (`Authorization: Basic base64(user:pass)`)

**Bearer Token** (e.g., Docker Hub, Quay, OIDC-backed registries):
- Omit `username` and `password`
- 401 response triggers token exchange at the registry's auth endpoint
- Token is cached and reused for subsequent requests

**No Auth** (public registries):
- Omit `username`, `password`, and all auth-related variables

### Proxy Configuration

Set proxy URL at role level or per-artefact:

```yaml
raw_artefact_https_proxy: http://proxy.example.com:3128
raw_artefact_no_proxy: "localhost,.internal.example.com"

raw_artefacts:
  - registry: docker.io
    repository: library/alpine
    reference: latest
    dest_path: /tmp/alpine
    create: true
    # This artefact uses role-level proxy settings

  - registry: internal.example.com
    repository: myorg/app
    reference: v1.0.0
    dest_path: /opt/app
    create: true
    # Per-artefact override (only for this artefact)
    https_proxy: http://different-proxy:3128
    no_proxy: "internal.example.com"
```

### TLS Control (Test vs Production)

**Production** (default):
```yaml
raw_artefact_tls_verify: true  # Use HTTPS (default)
raw_artefacts:
  - registry: docker.io
    repository: myorg/app
    reference: v1.0.0
    dest_path: /opt/app
```

**Test/Self-Signed Registry**:
```yaml
raw_artefact_tls_verify: false  # Use HTTP for test registry
raw_artefacts:
  - registry: localhost:5000  # Must be HTTP-only in test
    repository: myorg/app
    reference: v1.0.0
    dest_path: /opt/app
```

## Role Implementation

The role is wired end-to-end: `tasks/main.yml` loops over `raw_artefacts` and
invokes the `raw_artefact` module for each entry. Per-artefact parameters override
role defaults via Jinja2 `default()` filters, allowing flexible configuration.

## Configuration

### Registry Mirror

The role supports registry mirroring via precedence:
1. Per-artefact `registry_mirror` (highest precedence)
2. Role-level `raw_artefact_registry_mirror`
3. No mirror (use registry as-is)

When a mirror is set, the mirror hostname substitutes for the registry hostname
in all pull requests, but the repository path and reference remain unchanged.

### Proxy Settings

HTTP and HTTPS proxy configuration is supported via role defaults:
- `raw_artefact_http_proxy`
- `raw_artefact_https_proxy`
- `raw_artefact_no_proxy`

Each setting can be overridden per-artefact. Precedence (highest to lowest):
1. Per-artefact override
2. Role default
3. None

### Idempotency

The module tracks pulled artefacts via a marker file (`.raw_artefact_state.json`)
written to `dest_path`. On subsequent runs:
- If marker exists and composite digest/owner/group/mode all match, the pull is skipped
- Changed flag is false
- No downloads occur

To force a re-pull, delete the marker file from `dest_path`.

### Check Mode

The module supports Ansible check mode (`-C`):
- Validates input and registry connectivity
- Reports changed status correctly
- Does NOT download, extract, or write to `dest_path` in check mode
- Useful for testing playbooks without applying changes

## Testing

Molecule scenario (`molecule/default/`) verifies end-to-end role functionality:

### Test Coverage

- **Direct pull**: Fetch from primary registry without mirror
- **Mirror substitution**: Broken registry URL succeeding via mirror
- **Per-artefact override**: Override beats role default
- **Multi-layer artefacts**: Extract `.tar.gz` layers and place plain files
- **Credentialed auth**: Basic auth to htpasswd-protected registry
- **Failure path**: `create: false` correctly fails on missing `dest_path`
- **Idempotency**: Second converge run detects no changes (marker file)

### Running Tests

```bash
# Unit tests (45+ tests covering module logic)
make unittest

# End-to-end Molecule test (real Docker containers)
cd roles/raw_artefact_pull
molecule test

# Clean up test artifacts
make clean
```

### Test Infrastructure

Molecule uses a custom Docker network (`raw_artefact_test`) with:
- `target`: Ubuntu 22.04 with Ansible and Python
- `registry`: Docker Registry V2 (anonymous)
- `registry_auth`: Docker Registry V2 with htpasswd (Basic auth)

All three containers run on the same network for inter-container DNS resolution.

## Files

- `tasks/main.yml` — Role task loop over `raw_artefacts`
- `library/raw_artefact.py` — Core module (680+ lines)
- `library/test_raw_artefact.py` — Unit tests (47 tests)
- `molecule/default/` — End-to-end test scenario
  - `molecule.yml` — Docker driver config
  - `prepare.yml` — Fixture creation and push
  - `converge.yml` — Role execution (6 test plays)
  - `verify.yml` — Validation assertions (6 verify plays)

## Examples

See `molecule/default/converge.yml` and `molecule/default/verify.yml` for complete
working examples of all test cases (mirror, override, multi-layer, credentials, failure paths).
