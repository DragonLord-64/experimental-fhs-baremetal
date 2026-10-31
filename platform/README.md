# FHS platform

The development platform uses HTTP on the trusted provisioning LAN. Edit
[values-provisioning.yaml](values-provisioning.yaml) for the existing platform
hostname and LoadBalancer services, then follow the
[installation commands](charts/fhs-platform/README.md). No additional DNS names
or TLS Secrets are required. Keep the complete chart directory when copying it
to the cluster management host.

[Service addresses and client settings](charts/fhs-platform/CONFIGURATION.md#development-http-endpoints).
[Server log setup and shipping](../roles/filebeat/README.md).

HTTPS may be enabled later when certificates and a suitable TLS endpoint are
available. Upstream PyPI and Git HTTPS certificate verification remains enabled.

[Export platform secrets and endpoints for Ansible](charts/fhs-platform/README.md#export-ansible-settings).
