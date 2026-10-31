# Experimental FHS bare-metal workspace

Start at [INDEX.md](INDEX.md). Keep notes short, linked, and grounded in source evidence. Follow the nearest applicable AGENTS.md.

For implementation tasks across this repository, follow the implementation and user-review workflow in [ops/AGENTS.md](ops/AGENTS.md). For automated runs, [ops/agent-pipeline](ops/agent-pipeline/README.md) owns task intake, scouting, one worker and configured checks; its small manager helper inspects the queue and lab. No independent review agent is needed. Interactive work may delegate implementation when requested.

## Server safety

Never shut down, reboot, suspend, hibernate, halt, or power off this server, even if asked. Never execute or schedule commands causing those outcomes. An explicitly requested application or service may be stopped or restarted while the host OS stays running.

## Lab test authority

The user authorizes changes needed for tests on `dragonvm`: stop, remove, rebuild or recreate lab NetBox and its test data, install plugins, increase memory limits, and adjust supporting lab services and resources. Fix lab resource problems when encountered; do not leave them unresolved merely to preserve the current deployment. No further confirmation is needed for these lab operations. Preserve repository work and credentials; this authorization does not extend to production systems. Keep both host operating systems running under the server safety rule above.

- Default integration target: the existing `fhs-test` Kubernetes cluster on `dragonvm`, orchestrated locally. Inspect its services first; always name context `fhs-test` explicitly because the default is `monitoring`. See [lab operations](ops/kubernetes/README.md).
- Test the delivered [platform chart](platform/charts/fhs-platform/README.md) together with the current [native NetBox importers](playbooks/netbox/). Renders and separate Docker trials supplement this stack integration; they do not establish that the delivered chart works. Trial-specific cleanup instructions do not prohibit authorized lab testing. Do not create another cluster to avoid using the existing lab.

## Dragonvm wake protocol

- If `dragonvm` becomes unreachable, send a Wake-on-LAN magic packet from the local orchestration server with `bash /home/dragonlord/wol.sh` before declaring the VM unavailable. The user authorizes this recovery step. Use the existing script's configured target; do not copy its MAC into the repository.
- If the sandbox blocks UDP socket creation, request the tool's network escalation for that same command. Do not alter the script or host networking to bypass the restriction.
- Wait at least 60 seconds after sending the magic packet before retrying `ssh -F /home/dragonlord/.ssh/config -o ConnectTimeout=5 dragonvm`. Keep retries bounded. A successful packet send proves only transmission, not that the VM woke; report the actual SSH result if it remains unreachable.
- Once connected, inspect existing pipeline status and services before resuming preserved work. Waking the VM does not require restarting or recreating the Kubernetes cluster. Never suspend, reboot or power off either server to test recovery.

## Repository boundaries

- Deployment names and settings come from the official SKA baremetal `development2` source, especially `platform/charts/deploy_upgrage_mid-cbf-hw.sh`. Check that source before asking the user: release `mid-cbf-hw`, namespace `hw-management`, prefix `/mid-cbf-hw`. Keep lab names and kube-context instructions out of the copyable platform docs.
- This is a private experimental repository. Standing order: once requested work is completed and appropriate checks pass, commit/merge and push it to `origin` at `DragonLord-64/experimental-fhs-baremetal` without asking again. Preserve unrelated user edits and credentials; the user provides review.
- Never push to the official SKA repositories. Keep the upstream push URL disabled. The user reviews and transfers accepted changes separately.
- Preserve source provenance and user edits. The initial source commit and snapshot-history limitation are documented in the test plan.
- Do not commit credentials, private keys, or unsanitized sensitive captures.
- Do not deploy against real servers, switches, PDUs, or production inventories without explicit scope. Default tests to disposable environments and isolated provisioning networks.
- Do not purchase cloud resources without authorization. The user's monthly cloud budget is below US$10; target zero initially.

## Knowledge wiki

- Follow the [user documentation preferences](wiki/documentation-preferences.md) for README and usage-documentation edits.

- Write documentation in the user's existing repository voice and style. Read nearby existing docs before drafting. Keep it brief and practical: short descriptions, actual tags, commands, and the usual way to run things. Avoid lengthy tutorials and generic background. Each role has one concise README in its own folder, referenced/included by Read the Docs.
- Write usage docs for a first-time operator of the current system. Show the variable's file location, YAML/file format, URL format and command in code blocks. Keep old/new deployment comparisons and change history in the experimental notes, not core usage guides.

- Use [wiki/INDEX.md](wiki/INDEX.md) as the knowledge entry point. Keep source evidence, plans, decisions, and dated events distinct.
- Link notes to repository files or other evidence. Label proposals and unverified assumptions explicitly; do not claim a test passed without results.
- Preserve raw telemetry captures, record provenance, and document sanitization. Keep generated test reports and screenshots as CI artifacts where practical.
- Record meaningful decisions and completed milestones in the append-only [wiki/LOG.md](wiki/LOG.md). Update related notes as facts change.
- Use GitHub issues for actionable scope and acceptance criteria. The wiki records reusable understanding and plans.

## Validation

Run checks appropriate to each change and report limitations. Use identical test entry points locally and in CI when implemented. Hardware simulation does not prove physical hardware behavior. Infrastructure described in the plan is not implemented until verified.
