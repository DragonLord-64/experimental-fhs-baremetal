FROM quay.io/openstack.kolla/bifrost-deploy:2026.1-ubuntu-noble


# Install packages required for IPA and deployment image builds via diskimage-builder.
# mdadm/dracut are explicitly listed in ipa_build_dib_packages in group_vars.
# lvm2, dosfstools, gdisk are needed for the EFI+LVM block device layout.
# qemu-utils provides qemu-img for qcow2 image creation/conversion.
# qemu-kvm, ovmf, ebtables, libvirt-dev are needed for the libvirt test environment.
RUN apt-get update && apt-get install -y --no-install-recommends \
    mdadm \
    dracut \
    qemu-utils \
    qemu-kvm \
    ovmf \
    ebtables \
    lvm2 \
    dosfstools \
    gdisk \
    libvirt-daemon-system \
    libvirt-clients \
    libvirt-dev \
    python3-libvirt \
    virtinst \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# OVMF on Ubuntu Noble ships only the 4 MiB firmware variants (OVMF_*_4M.fd).
# bifrost's libvirt XML logic can end up writing the legacy 2 MiB paths
# (OVMF_CODE.fd / OVMF_VARS.fd) into the domain XML; libvirt then fails at VM
# start because those files don't exist. Symlink the legacy names to the 4M
# variants so either resolution works.
RUN ln -sf /usr/share/OVMF/OVMF_CODE_4M.fd /usr/share/OVMF/OVMF_CODE.fd \
 && ln -sf /usr/share/OVMF/OVMF_VARS_4M.fd /usr/share/OVMF/OVMF_VARS.fd

# Ensure diskimage-builder is current so all elements and block-device plugins are available.
RUN pip install --upgrade diskimage-builder

# Install the custom block-device-efi-lvm DIB element.
# This element is not in upstream DIB; it enables the YAML-based EFI+LVM partitioning
# defined in image-config/fhs-block-device-*.yaml via DIB_BLOCK_DEVICE_CONFIG.
COPY dib-elements/block-device-efi-lvm /usr/share/diskimage-builder/elements/block-device-efi-lvm

# Install Ansible collections needed for test environment (openvswitch is statically
# imported in bifrost-create-vm-nodes and must be resolvable even when the OVS tasks
# are conditionally skipped).
RUN ansible-galaxy collection install openvswitch.openvswitch

# Generate an SSH keypair so ssh_public_key_path and DIB_DEV_USER_AUTHORIZED_KEYS
# resolve correctly during install and image build.
RUN python3 -c "\
from cryptography.hazmat.primitives import serialization; \
from cryptography.hazmat.primitives.asymmetric import rsa; \
from cryptography.hazmat.backends import default_backend; \
import os; \
key = rsa.generate_private_key(public_exponent=65537, key_size=2048, backend=default_backend()); \
os.makedirs('/root/.ssh', mode=0o700, exist_ok=True); \
open('/root/.ssh/id_rsa','wb').write(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.OpenSSH,serialization.NoEncryption())); \
os.chmod('/root/.ssh/id_rsa',0o600); \
open('/root/.ssh/id_rsa.pub','wb').write(key.public_key().public_bytes(serialization.Encoding.OpenSSH,serialization.PublicFormat.OpenSSH)+b' root@bifrost\n')"

# Override dnsmasq systemd service for container use.
# The default forking+PID-file mode fails because the container cgroup hierarchy
# prevents systemd from accepting PIDs written by the dnsmasq user.  Running in
# foreground (-k) with Type=simple lets systemd track the process directly.
RUN mkdir -p /usr/lib/systemd/system/dnsmasq.service.d && \
    printf '[Service]\nType=simple\nPIDFile=\nExecStart=\nExecStart=/usr/sbin/dnsmasq -k -u dnsmasq -r /run/dnsmasq/resolv.conf -7 /etc/dnsmasq.d,.dpkg-dist,.dpkg-old,.dpkg-new\nExecStartPost=\n' \
    > /usr/lib/systemd/system/dnsmasq.service.d/container.conf

# Activate the kolla venv for all container processes and point the OpenStack
# client at the pre-configured bifrost cloud entry in /root/.config/openstack/clouds.yaml.
ENV VIRTUAL_ENV=/var/lib/kolla/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
ENV OS_CLOUD=bifrost

# Also source the venv for interactive bash sessions (exec into the container).
RUN echo 'source /var/lib/kolla/venv/bin/activate' >> /etc/bash.bashrc && \
    echo 'export OS_CLOUD=bifrost' >> /etc/bash.bashrc

# Update package list, install packages, and clean up in a single layer
RUN apt-get update && apt-get install -y \
    openssh-client \
    nano \
    && rm -rf /var/lib/apt/lists/*

RUN pip install ansible-dev-tools