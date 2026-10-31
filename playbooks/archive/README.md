# Archived playbooks

Historical entry points retained for reference; they are not part of the current workflow. Archiving does not make their commands safe to execute.

| Playbook | Provenance and current direction |
|---|---|
| `audit_ubuntu_cis.yml` | Former standalone CIS audit; its existing artifacts remain under `playbooks/artifacts/`. No new audit workflow is claimed. |
| `run_ubuntu_cis.yml` | Former standalone prototype remediation. Review the current `site.yml` CIS scope and policy before selecting its `ubuntu24_cis` tag. |
| `node_setup.yml` | Former node wrapper; current wrapper: `site.yml --tags setup_k8s_node`. |
| `install_bist.yml` | Former BIST wrapper; current wrapper: `site.yml --tags manage_fhs_bist`. |
| `install_grpc.yml` | Archived controller installation wrapper. FSP/VCC services remain supported by `manage_fhs_grpc`; certificate-update is separate one-off security remediation. |
| `install_prometheus.yml` | Former exporter/Prometheus wrapper; current wrapper: `site.yml --tags manage_fhs_exporter,manage_prometheus`. |
| `exds_configure.yaml` | Former machine-specific EXDS Netplan/Puppet setup, including fixed network settings and a private Puppet backup path. No general replacement is claimed. |
| `filebeat_setup.yml` | Former development wrapper; current wrapper: `site.yml --tags filebeat`. |

Current wrappers are relative to `playbooks/` and require explicitly authorized inventory and protected variables. Review note: original bodies are preserved except the CIS audit's two artifact paths, which now traverse to the same existing directory; the path adjustment has an inline comment. No playbook was executed. `site.yml`, `provision.yml`, `updated_bmc_bios.yml` and remaining development files, including `install_card_test.yml`, remain in place.
