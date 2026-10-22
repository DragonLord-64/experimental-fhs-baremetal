# Using NetBox For Ansible Inventory

Inventory files are the main method of defining the hosts that will be used by Ansible to run playbooks against. Currently, the inventory consists of a main inventory file that defines facts such as the endpoint and hardware configuration, as well as host and group variables that define the configuration for a specific host and the groups it can belong to, respectively.

Currently, there are two main ways to define the hardware configuration and host variables, local `.yml` files, and the [NetBox service](https://netboxlabs.com/docs/netbox/). 

## Polling Netbox for Inventory
To poll NetBox from Ansible, the [Netbox plugin](https://docs.ansible.com/projects/ansible/latest/collections/netbox/netbox/nb_inventory_inventory.html#ansible-collections-netbox-netbox-nb-inventory-inventory) is used to poll the inventory stored there. This is done by creating a `.yml` file that defines access to the netbox, and how the format the data returned from it. At minimum, this file should consist of: 
```yaml
plugin: netbox.netbox.nb_inventory       # Defines plugin to use
api_endpoint: https://<ENDPOINT>/netbox/ # Defines the endpoint where NetBox is set up
validate_certs: false                    # As we use internal hosting for Netbox, do not need to validate the certificate of the endpoint for now
token:
  type: Bearer                           # Define a bearer token is being used for access
  value: <VAULT ENCODED TOKEN>           # A generated token for a user with access to the NetBox service
```
Access can be confirmed by Sending a GET request to `https://<ENDPOINT>/netbox/api/dcim/devices` with the token, and ensuring it returns the expected list of devices.

For the token, ensure that it is encrypted via the [Vault Utility](https://docs.ansible.com/projects/ansible/latest/cli/ansible-vault.html#encrypt-string), and that a Vault password file is available for decryption.

When running with notebooks consider adding the following the the file as well:
```yaml
query_filters:
  - status: "active" # Make sure only active devices are retrieved.
use_extra_vars: true # Pull in the extra variables, such as those from the group variable files
```

### Validating NetBox Inventories
Once the file is set up, it can be checked by running:
```shell
ansible-inventory -i "<PATH TO NETBOX .YML FILE>" --list -y --output "inventory/netbox-output.yml" 
```
This will check that the NetBox is available and parseable by Ansible, and allows for manual verification of the inventory. The `--host <HOST_ID>` can also be set to check a specific target host.

*Automatic validation methods to come later.*

## Using NetBox In Playbooks
Using the Netbox inventory is straightforward, as once validated, the NetBox `.yml` file can be used in place of a regular inventory `.yml` file. For example:
```shell
ansible-playbook -i "<PATH TO NETBOX .YML FILE>" "<PATH TO PLAYBOOK FILE>" --tags "<TAGS TO RUN>"
```
Note that if not running in the same directory with a subdirectory of `group_vars` these will need to be specified using the extra variables flag (`-e <LINK TO GROUP VARS FILE>` ) for each group that playbook needs.
