# manage_fhs_bist

Installs and configures the Built-in Self Test (BIST) on a FHS server. This role installs the BIST software from an external source (GitLab) and sets up the necessary environment, virtual environments, and directory structures.

## Requirements

No prerequisites are required prior to running this role.

## Usage

All configuration parameters—including hardware BDFs, serial numbers, repository versions, and installation paths—are managed via `defaults/main.yml`. To customize the installation for a specific server, override these variables in your inventory file.

For a complete list of configurable parameters, please see the [role documentation](/docs/src/roles/bist.md).


## License

BSD-3-Clause