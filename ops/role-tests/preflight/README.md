# Preflight fixture

Run with Ansible, the declared collections, OpenSSL and `dpkg-deb` installed:

```sh
python3 ops/role-tests/preflight/check.py
```

Uses temporary files and local HTTP/HTTPS servers. It runs the actual preflight
playbook against a local synthetic inventory, without provisioning a host.
Checks success with zero changes, missing artifacts, bad credential fields,
untrusted certificates, insecure pip URLs, HTTPS downgrade redirects, input-only
bootstrap. Input file hashes remain intact;
secret values must not appear in output. Logs are `/tmp/fhs-preflight-*.log`.

2026-10-30: all cases passed. Provisioning/preflight/Filebeat setup syntax and
source/link checks passed; Sphinx HTML built. No production or lab deployment,
CI change or repair of the previously recorded temporary importer tests.
