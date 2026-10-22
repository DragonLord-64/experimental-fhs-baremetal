block-device-efi-lvm
====================

Custom element that enables EFI + LVM partitioning via a YAML block device
configuration file passed through ``DIB_BLOCK_DEVICE_CONFIG``.

This element declares a dependency on the ``vm`` element (which activates DIB's
block-device plugin) and otherwise defers all partitioning logic to the YAML
spec defined in ``image-config/fhs-block-device-*.yaml``.

Required environment variable
------------------------------

``DIB_BLOCK_DEVICE_CONFIG``
    ``file://`` URI pointing to the block device YAML inside the container,
    e.g. ``file:///bifrost/playbooks/fhs-block-device-2026-05-12-noble.yaml``.
    Set in ``image-config/fhs-image-config-*.yaml``.
