# To-do

Documentation backlog captured 2026-10-21. Provisioning/monitoring reconciliation is integrated in the existing [Sphinx guides](../docs/src/guide/guide.rst), [development procedures](../docs/src/playbooks/development.md) and canonical role READMEs. Independent source/integration review passed; runtime limitations remain in the linked validation pages.

Style requirement: match the user's existing documentation voice. Keep descriptions short and practical, with tags and normal usage; use existing docs as writing references.

- [x] Consolidate each role's documentation into one brief `README.md` inside its role directory: purpose, behavior, tags, usual invocation, and essential prerequisites or cautions. Reference/include that same README from the Sphinx docs for Read the Docs; avoid duplicate prose. Preserve the existing documentation structure and diagrams where useful.
- [x] Document NetBox setup and usage: inventory, profile/group mapping, overrides, and importing devices and related data.
- [x] Document the current monitoring architecture and deployment, including how telemetry reaches its consumers.
- [ ] Document Grafana setup, data sources, dashboard provisioning, and normal usage.
- [x] Review development playbooks and document those now used operationally, including NetBox imports; distinguish supported workflows from experiments.
- [x] Document switch POAP provisioning in `playbooks/development/switch-poap/`, including the POAP script, Nexus configuration, and Bifrost DHCP integration.
- [x] Check documented commands, tags, paths, and diagrams against current code, then verify the Read the Docs build and links.

Keep entries concise. Move executable scope and acceptance criteria into GitHub issues when work begins.
