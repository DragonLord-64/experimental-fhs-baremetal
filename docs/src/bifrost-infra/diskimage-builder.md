# Disk Image Builder

The `bifrost-infra/` container uses host networking and privilege. Review the target network before running it. Bifrost playbooks are supplied by the image under `/opt/bifrost/playbooks`.


This software can be used to construct custom images.

For more details see the documentation: https://opendev.org/openstack/diskimage-builder/src/branch/master


## Example Usage

Define the image
[image-config](../../../bifrost-infra/image-config/fhs-image-config-2026-05-12-noble.yaml)
```yaml
---
- imagename: fhs_image_2026-05-12_noble.qcow2
  elements: [ base, ubuntu, vm, growroot, block-device-efi-lvm, cloud-init-datasources]
  image-size: 925
  environment:
    DISTRO_NAME: ubuntu
    DIB_RELEASE: noble
    DIB_CLOUD_INIT_DATASOURCES: "Ec2, ConfigDrive, OpenStack"
    DIB_BLOCK_DEVICE_CONFIG: "file:///bifrost/playbooks/fhs-block-device-2026-05-12-noble.yaml"
```
**Note** Must reference the block device file from this file. Use 3x '/' at the begining: "file:///..."


Define the partition structure
[block-device](../../../bifrost-infra/image-config/fhs-block-device-2026-05-12-noble.yaml)
```yaml
- local_loop:
    name: image0
- partitioning:
    base: image0
    label: gpt
    partitions:
      - name: ESP
        type: EF00
        size: 512MiB
        mkfs:
          type: vfat
          mount:
            mount_point: /boot/efi
            fstab:
              options: "defaults"
              fsck-passno: 2   # 0 is also fine for ESP
      - name: BSP
        type: 'EF02'
        size: 8MiB
      - name: root
        type: '8300' 
        flags: [boot]  
        size: 100%
- lvm:
    name: lvm
    base: [ root ]
    pvs:
      - name: pv
        base: root
        options: ["--force"]
    vgs:
      - name: vg
        base: ["pv"]
        options: ["--force"]
    lvs:
      - name: lv_root
        base: vg
        extents: 22%VG
      - name: lv_tmp
        base: vg
        extents: 4%VG
      - name: lv_var
        base: vg
        extents: 25%VG
      - name: lv_log
        base: vg
        extents: 16%VG
      - name: lv_audit
        base: vg
        extents: 5%VG
      - name: lv_home
        base: vg
        extents: 18%VG
- mkfs:
    name: fs_root
    base: lv_root
    type: xfs
    label: "img-rootfs"
    mount:
      mount_point: /
      fstab:
        options: "rw,relatime"
        fsck-passno: 1
- mkfs:
    name: fs_tmp
    base: lv_tmp
    type: xfs
    mount:
      mount_point: /tmp
      fstab:
        options: "rw,nodev,relatime"
        fsck-passno: 2
- mkfs:
    name: fs_var
    base: lv_var
    type: xfs
    mount:
      mount_point: /var
      fstab:
        options: "rw,relatime"
        fsck-passno: 2
- mkfs:
    name: fs_log
    base: lv_log
    type: xfs
    mount:
      mount_point: /var/log
      fstab:
        options: "rw,relatime"
        fsck-passno: 2
- mkfs:
    name: fs_audit
    base: lv_audit
    type: xfs
    mount:
      mount_point: /var/log/audit
      fstab:
        options: "rw,relatime"
        fsck-passno: 2
- mkfs:
    name: fs_home
    base: lv_home
    type: xfs
    mount:
      mount_point: /home
      fstab:
        options: "rw,nodev,relatime"
        fsck-passno: 2
```

Execute the build process

```bash
diskimage-builder image-config.yaml # path to image config file.
```






