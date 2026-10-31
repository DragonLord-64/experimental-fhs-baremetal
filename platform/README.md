# FHS platform

The development platform uses HTTP on the trusted provisioning LAN. Edit
[values-provisioning.yaml](values-provisioning.yaml) for the existing platform
hostname and LoadBalancer services, then follow the
[installation settings](charts/fhs-platform/README.md). No additional DNS names
or TLS Secrets are required. Keep the complete chart directory when copying it
to the cluster management host.

Install or update, then export the credentials and endpoints using the current
Kubernetes context:

```bash
platform/deploy.sh
```

The helper waits for Helm to succeed before exporting to
`platform/charts/platform-export/`. It uses release `mid-cbf-hw` and namespace
`hw-management`. Edit `values-provisioning.yaml` before running it.

[Service addresses and client settings](charts/fhs-platform/CONFIGURATION.md#development-http-endpoints).
[Server log setup and shipping](../roles/filebeat/README.md).

HTTPS may be enabled later when certificates and a suitable TLS endpoint are
available. Upstream PyPI and Git HTTPS certificate verification remains enabled.

[Export platform secrets and endpoints for Ansible](charts/fhs-platform/README.md#export-ansible-settings).

[Quick password lookup commands](charts/fhs-platform/README.md#get-passwords).
