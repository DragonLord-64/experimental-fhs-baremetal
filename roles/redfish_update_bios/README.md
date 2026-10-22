# BIOS Update

**WARNING: As this modifies the motherboard, it can possibly corrupt the image and render the MB unresponsive. Proceed with Caution.**

**WARNING: According to the latest ASRock images, BMC should be updated BEFORE the BIOS is updated**

This role manages the BIOS for a target motherboard. Using a BIOS image (`.ROM`) provided in the `/files` and set in the vars, it starts the flashing process. Once this is done, the system can be reset and the update applied.

## References

As this interacts with a number of services, and impacts hardware, review the tooling used for this:
- [Redfish whitepaper for upgrade command](https://www.dmtf.org/sites/default/files/standards/documents/DSP0266_1.21.0.html#multipart-http-push-updates).
- [Ansible module for working with Redfish](https://docs.ansible.com/projects/ansible/latest/collections/community/general/redfish_command_module.html).
- [ASRock examples for upgrading via Redfish](https://www.asrockrack.com/support/faq.asp?k=redfish).

## Variables

The following variables are defined in the main.yaml file in the `/defaults` directory and are used by the Prometheus playbook.

* `redfish_update_bios_image`: The ASRock-supplied image to apply to the BIOS, stored in the files directory.

In addition, the following must defined under the `redfish` section for host variables:
* `address`: The IP endpoint for redfish API calls.
* `username`: Username to use for Redfish access. Currently the commands are written that this will be admin-level.
* `password`: Password for the user.

## Usage

To upgrade the BMC, call the `rf_update_bios` tag. This will use the file specified in the `redfish_update_bios_image` variable and call the [Redfish multipart HTTP push update ](https://www.dmtf.org/sites/default/files/standards/documents/DSP0266_1.21.0.html#multipart-http-push-updates)to load the binary into the Update Service. Once this is completed, the update service will start the flashing process, which can be verified by checking `https://<RF_IP>/redfish/v1/UpdateService` and validating that `Oem/AMIUpdateService` has the "Flashing" status. Once this is completed, the system can be restarted.