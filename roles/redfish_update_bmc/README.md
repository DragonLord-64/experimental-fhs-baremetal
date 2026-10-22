# Baseboard Management Controller Update

**WARNING: As this modifies the motherboard, it can possibly corrupt the image and render the MB unresponsive. Proceed with Caution.**

This role manages the BMC for a target motherboard. Using a BMC image (`.img`) provided in the `/files` and set in the vars, it uses Redfish to prep for an upgrade, when the motherboard is restarted, the BMC will be upgraded.

## References

As this interacts with a number of services, and impacts hardware, review the tooling used for this using the following documents:
- [Redfish whitepaper for upgrade command](https://www.dmtf.org/sites/default/files/standards/documents/DSP0266_1.21.0.html#multipart-http-push-updates).
- [Ansible module for working with Redfish](https://docs.ansible.com/projects/ansible/latest/collections/community/general/redfish_command_module.html).
- [ASRock examples for upgrading via Redfish](https://www.asrockrack.com/support/faq.asp?k=redfish).

Redfish updates are done via HTTP POST commands, which are handled by the

## Variables

The following variables are defined in the main.yaml file in the `/defaults` directory and are used by the Prometheus playbook.

* `redfish_update_bmc_image`: The ASRock-supplied image to apply to the BMC, stored in the files directory.

In addition, the following must defined under the `redfish` section for host variables:
* `address`: The IP endpoint for redfish API calls.
* `username`: Username to use for Redfish access. Currently the commands are written that this will be admin-level.
* `password`: Password for the user.

## Usage

To upgrade the BMC, call the `rf_update_bmc` tag. This will use the image file specified by `redfish_update_bmc_image` and call the [Redfish multipart HTTP push update ](https://www.dmtf.org/sites/default/files/standards/documents/DSP0266_1.21.0.html#multipart-http-push-updates)to load the binary into the Update Service. Once this load is completed, validate that the new image has been added to the redfish endpoint by visiting `https://<RF_IP>/redfish/v1/UpdateService/FirmwareInventory/BMC` and verifying "version" matches. Now, the next restart will cause the image to be applied. This can be done by calling the `rf_restart` tag.
