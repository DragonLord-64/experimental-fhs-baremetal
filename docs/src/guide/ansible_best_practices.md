# Ansible Best Practises and Style Guide

This document describes the best practises to use when creating and updating the Ansible playbooks used to manage deployed systems.

It will touch on the formatting, naming and other best practises of:
- General file structures and naming schemes
- How to Format and best practises for ansible playbooks themselves
- Best uses of variables, and their naming.
- Task definition and naming conventions
- How to use and define tags

## General Formatting

### Directory Structure

For ease of reference, all playbooks and tasks should follow the same directory structure.

```
playbooks/ 
roles <-- Contains all roles that can be executed by playbooks
└── example_role  <-- A logical grouping of tasks and related items
    ├── defaults  <-- Default variable values to use, can be overridden via command line or by values in the vars directory
    │   └── ...
    ├── files     <-- All misc files that tasks may need to execute, such as binary files
    │   └── ...
    ├── handlers  <-- Plays that are called via notifications rather than in sequence
    │   └── ...
    ├── meta      <-- Contains the metadata file for the role
    │   └── ...
    ├── README.md
    ├── tasks     <-- The actual tasks that are used by this role
    │   └── ...
    ├── templates <-- .j2 files that provide templates for files built by Ansible tasks
    │   └── ...
    ├── molecule  <-- Contains the data that molecule will use when testing
    │   └── ...
    └── vars      <-- Variable overwrites
        └── ...
├── playbook.yml
└── <TOP LEVEL FILES>
```
### General Playbook Files
At the task level, a readme markdown file should be provided to give a summary of the what is done by the tags in the tasks file, as well as a summary of the variables. Development and deployment can also be assisted by defining a requirements.yml file to specify what is required by the playbooks, such as additional collections.

## Playbook Formatting

General playbook formatting can be checked by running the linter against the file. Playbooks should be focused on a single element, such a service or group of settings. Within this playbook, reference any tasks that will impact that service, such as (un)installation, or configuration.

### Example playbook format:
```
- name: <Name for grouping of tasks>
    hosts: <Subgroup of hosts to target by default>
    become: true
    gather_facts: <Set to true if tasks will use system information>
    tasks:
        - name: <name of the task to run under the tag>
        - name: "
    tags:[<tags which should run this job when called>]
```

## Roles

### Role naming
Roles should follow the naming scheme of `<action>_<item>` (for example, `install_prometheus`).

## Variables

### Variable naming
In general, variables that are used by a role should be given the prefix of the task they will be used for (e.g variable `pip_install_version` would be used for task `pip_install`)

### Precedence
Variable in Ansible have precedence applied to them, that is, variables may be overridden by setting the variable in a different location. For our usage, the most relevant of these are (in order from highest precedence to lowest):


1. Extra CLI variables `-e "var_name=value"`
2. Role variables in `vars` directories 
3. Inventory file variables 
4. Role variables in `default` directories.

A more complete list can be found in the [Anisble documentation](https://docs.ansible.com/projects/ansible/latest/playbook_guide/playbooks_variables.html#variable-precedence-where-should-i-put-a-variable).

## Tasks

### General

- When calling tasks, use the full FQDN for it when calling. For example use `ansible.builtin.task` instead of purely `task`. This helps reduce ambiguity.

- If needing tasks that do not have a definite failed or completed state, such as the `command` task, define a `changed_when` argument. This will ensure the playbook is idempotent (has consistent behaviour regardless of deployment and run), and allow listener tasks to be called if required.

- The `command` task is preferred over the `shell` task when running simple commands, due to speed improvements. Use the `shell` when piping or chained commands are required. If possible, find ways to not use these two commands and instead use the specialized tasks.

### Files 

Tasks should be split by behaviour into separate .yml files and named appropriately, such as `install_service.yml`. When building out playbooks, these can then be imported individually using the `ansible.builtin.import_tasks` task and applying the relevant tag to the task. For example: 
```
- name: Task Name
    ansible.builtin.import_tasks:
    file: roles/name/tasks/main.yml
    tags: [relevant_tag]
```
By splitting tasks between files, it allows for more definitive tagging, and prevents accidentally running unintended tasks.

## Handlers
If a task should be only be run when changes are made to the system. For example, a service may look for a configuration file when started, and therefore need to be restarted if that file changes. In such cases, the restart behaviour (or any other behaviour that occurs on change) should be moved to a YAML file under the handler directory. To trigger a handler, add `notify: <handler name>` to the task you want the handler to occur after.

## Tags
Tags limit the selection of certain tasks, making them an important way of preventing unintentional behaviour.

### Usage
Use tags on the playbook level only, to tag roles as noted above. When Ansible compiles/runs, it applies tags downwards, such that any task called from a tagged role will also be given that tag.

### Tag naming
It is important to note that when running, Ansible uses **or** comparison logic when multiple tags are requested. For example, if `--tags foo,bar` is called, any job with **either** foo or bar will be called. 
Therefore, avoid common language tags such as `install` while testing/developing, as attempting to call with this tag may trigger other tasks. Instead, use the base format of `<action>_<item>` (for example, `install_prometheus`).

## Templates
Templates are to be used for increasing the flexibility of configuration files, or any other files that need to be edited run-to-run. Templates use the Jinja templating engine, so any template file must add the `.j2` file type. Templates can then use vars. To use templates, call the `ansible.builtin.template` task, which will fill in the variables and load it to the targets.

## Linting
Linting is handled by [Ansible Lint](https://docs.ansible.com/projects/lint/), and is automatically executed by the pipeline automatically, it can also be run locally using the `make ansible-lint` command. Linting follows the rules defined within the `.ansible-lint` file, which describes which warnings and errors to skip.

Currently this file also contains mock hosts to prevent linting errors from the molecule files.

### Linting in VSCode
If using VSCode for programming, the [relevant extension](https://marketplace.visualstudio.com/items?itemName=redhat.ansible) can be used to lint files live while developing. To use, attach VScode to your dev container and add to your `.vscode` file:
```
"ansible.validation.lint.arguments": "-c .ansible-lint"
```
Or manually edit via the UI under Ansible settings.