# Manage Poetry

Installs [Poetry](https://python-poetry.org/) with `/opt/venvs/fhs/bin/pip install poetry`, then checks `poetry --version`. The existing `/opt/venvs/fhs` environment and its pip index/proxy configuration are prerequisites; see the `manage_venvs` and `setup_pip_source` roles.

## Variables

No role defaults or role-specific variables are defined. The virtual environment path is fixed in `roles/manage_poetry/tasks/main.yml`.

## Tags/Usage

From the repository root, select the role through the site playbook:

```bash
ansible-playbook -i <INVENTORY> playbooks/site.yml --limit <HOST> --tags manage_poetry
```

`manage_poetry` selects the wrapper and applies to its tasks; `poetry_install` tags both installation and version checking. Uninstall tasks are commented out and no removal operation is implemented.
