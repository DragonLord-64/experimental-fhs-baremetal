# Knowledge wiki

Start here for current understanding and recorded evidence. Commands belong in
the linked source/operations READMEs; dated results do not prove current service
health. Keep proposals separate from implemented behavior and append completed
work to the [log](LOG.md).

## Topics

| Topic | Current note | Commands and evidence |
|---|---|---|
| Test environment and remaining gaps | [Environment plan](test-environment-plan.md) | [VM access/lifecycle](../ops/kubernetes/README.md), [platform lab](../ops/platform/README.md), [Bifrost isolation](../ops/provisioning/README.md) |
| NetBox identity, assets and controller resources | [Ownership and reconciliation](resource-layout.md) | [Importer](../playbooks/netbox/README.md), [asset/FRU acceptance](../ops/platform/inventory-alignment/VALIDATION.md) |
| LLDP and FPGA DAC connections | [Topology import](topology-import.md) | [Native acceptance](../ops/platform/inventory-alignment/README.md#lldp-and-dac-topology) |
| Dashboards and telemetry | [Demo versus observed data](latest-changes.md), [VCC/FSP units](unit-topology.md) | [Dashboard sources](../ops/dashboards/README.md), [static demo](../examples/grafana-static-demo/README.md), [captures](../ops/telemetry/README.md) |
| Logging and installation home | [Environment evidence](test-environment-plan.md#recorded-validation) | [Logging fixture](../ops/platform/logging/README.md), [device role](../roles/filebeat/README.md), [installation home](../ops/platform/landing-page/README.md) |
| Task execution and scope | [Task creation and focused acceptance](task-creation.md), [decisions](decisions.md#confirmed-with-the-user--2026-10-24-pipeline-cleanup) | [Task intake/scout/manager](../ops/agent-pipeline/README.md), [worker rules](../ops/AGENTS.md) |
| Source provenance and transfer | [Source map](sources.md), [copy boundary](source-boundary.md) | [Preserved-source manifest](../ops/source-boundary/PROVENANCE.json) |

## Decisions and history

- [Confirmed decisions and open questions](decisions.md)
- [Documentation backlog](TODO.md)
- [Append-only dated log](LOG.md)
- [Retired handoff map](HANDOFF.md)

## Wiki checks

From the repository root:

```sh
python3 ops/agent-pipeline/checks.py wiki/*.md
```

This checks local file links and whitespace. Inspect linked headings when moving
sections; it does not test external URLs or build Sphinx.
