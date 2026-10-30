# FHS platform

Edit [values-provisioning.yaml](values-provisioning.yaml) for the deployed site's
hostnames, TLS Secrets and LoadBalancer services. Create the proposed DNS records
and certificates, then follow the [installation commands](charts/fhs-platform/README.md).
Keep the complete chart directory, including dependencies, dashboards and image
sources, when copying it to the cluster management host.

[HTTPS and service settings](charts/fhs-platform/CONFIGURATION.md).
[Server log setup and shipping](../roles/filebeat/README.md).
