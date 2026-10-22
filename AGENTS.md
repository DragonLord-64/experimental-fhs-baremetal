# Experimental FHS bare-metal workspace

Start at [INDEX.md](INDEX.md). Keep notes short, linked, and grounded in source evidence. Follow the nearest applicable AGENTS.md.

## Server safety

Never shut down, reboot, suspend, hibernate, halt, or power off this server, even if asked. Never execute or schedule commands causing those outcomes. An explicitly requested application or service may be stopped or restarted while the host OS stays running.

## Repository boundaries

- This is a private experimental repository. Push authorized experimental work only to `origin` at `DragonLord-64/experimental-fhs-baremetal`.
- Never push to the official SKA repositories. Keep the upstream push URL disabled. The user reviews and transfers accepted changes separately.
- Preserve source provenance and user edits. The initial source commit and snapshot-history limitation are documented in the test plan.
- Do not commit credentials, private keys, or unsanitized sensitive captures.
- Do not deploy against real servers, switches, PDUs, or production inventories without explicit scope. Default tests to disposable environments and isolated provisioning networks.
- Do not purchase cloud resources without authorization. The user's monthly cloud budget is below US$10; target zero initially.

## Knowledge wiki

- Write documentation in the user's existing repository voice and style. Read nearby existing docs before drafting. Keep it brief and practical: short descriptions, actual tags, commands, and the usual way to run things. Avoid lengthy tutorials and generic background. Each role has one concise README in its own folder, referenced/included by Read the Docs.

- Use [wiki/INDEX.md](wiki/INDEX.md) as the knowledge entry point. Keep source evidence, plans, decisions, and dated events distinct.
- Link notes to repository files or other evidence. Label proposals and unverified assumptions explicitly; do not claim a test passed without results.
- Preserve raw telemetry captures, record provenance, and document sanitization. Keep generated test reports and screenshots as CI artifacts where practical.
- Record meaningful decisions and completed milestones in the append-only [wiki/LOG.md](wiki/LOG.md). Update related notes as facts change.
- Use GitHub issues for actionable scope and acceptance criteria. The wiki records reusable understanding and plans.

## Validation

Run checks appropriate to each change and report limitations. Use identical test entry points locally and in CI when implemented. Hardware simulation does not prove physical hardware behavior. Infrastructure described in the plan is not implemented until verified.
