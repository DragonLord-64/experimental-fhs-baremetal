# Documentation preferences

Confirmed by the user on 2026-10-30. Apply these preferences to repository
READMEs and usage docs. The [Bifrost quickstart](../docs/src/bifrost-infra/QUICKSTART.md)
is the reference for practical commands and configuration examples.

## Write for the operator

Answer “How do I use this?” Keep descriptions short and show the commands that
produce the intended result, what they do, and the settings the operator can
change. Describe the current system for someone reading it for the first time.
Do not assume knowledge of earlier deployments, changes or conversations.

For configuration, show:

- The exact file containing the variable.
- The variable name and a complete YAML or file-format example.
- The expected path or URL format, including required prefixes and ports.
- The command to use the configuration and, where useful, preview its scope.

Use code blocks and clear placeholders for private values. Match examples to
the configured workflow: Bifrost already reads the Vault password file, so its
Ansible examples do not need `--ask-vault-pass`.

## Keep each document about its subject

A role README explains what that role does, its inputs and how to use it. Avoid
unrelated commentary about whether `site.yml` includes it, temporary cleanup,
retirement history or the reason a recent change was made. Describe playbook
selection and orchestration in the playbook docs. Document the one-off
certificate security remediation in its own playbook guide.

Keep implementation explanations brief; the code supplies the detailed
implementation. Each role has one concise README included by Read the Docs.

## Document the provisioning environment

Core READMEs and docs describe the deployed cluster, separate platform servers
and provisioning host. Use the actual inventory structure and explain which
machine owns a file or runs a command when that affects use. Keep temporary lab
setup, test-specific commands and test results outside the core documentation,
in experimental operations notes or the wiki.

## Make focused edits

Preserve the repository's existing voice and the user's deliberate README
deletions. Do not restore deleted pages or rewrite everything for completeness.
Review affected docs for whether an operator can quickly use and modify the
feature. Keep change history, migration comparisons and dated validation in
experimental notes and the [log](LOG.md).
