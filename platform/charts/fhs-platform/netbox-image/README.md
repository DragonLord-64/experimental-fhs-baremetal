# NetBox Inventory image

NetBox `4.7.0` (base digest in Dockerfile), MIT `netbox-inventory==2.7.1`.
Plugin installation and static collection happen at build time. Web, worker and
housekeeping use the same image. No runtime pip command is needed.

From the copied `fhs-platform` folder:

```bash
bash netbox-image/build.sh                         # local image
NETBOX_IMAGE=registry.example/team/netbox-inventory:4.7.0-2.7.1 \
  bash netbox-image/build.sh --push                 # your existing registry
```

For a registry, set `netbox.image.registry`, `repository`, `tag`, and optionally
`digest` in your private values; provide namespace-local image pull credentials
when required. Every Kubernetes node must be able to pull that image. For an
isolated single-node lab, `bash platform/netbox-image/build.sh --lab` builds and
loads the default tag into the existing `fhs-test` profile. A local Docker build
alone does not make an image available to Kubernetes nodes.

The default tag is `fhs/netbox-inventory:4.7.0-2.7.1` with `IfNotPresent`.
Build/load or publish it before Helm installation. Record your registry digest
for reproducible deployment; the custom image is not published by this repo.
`platform/netbox-image` and the old trial recipe link here.
