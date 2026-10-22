# Decisions and open questions

## Confirmed with the user — 2026-10-21

- Use a private GitHub experimental repository and a separate checkout in the home directory.
- The agent may push experimental changes there; the user transfers accepted changes to official SKA repos.
- The user plans to set up a Linux VM using Hyper-V on a Windows gaming PC.
- Cloud spending must be below US$10 per month; use existing hardware first.
- Keep a short plan and a linked knowledge wiki inspired by DragonMind.
- Grafana dashboards are a workflow example; detailed dashboard scope is deferred.

## Proposed, not implemented

- Fast lint and syntax checks, disposable Kubernetes tests, VM provisioning tests, and separate physical hardware verification.
- A test runner on the Linux VM, with identical local and CI commands.
- Captured telemetry fixtures, dashboard query checks, and screenshot artifacts for issue review.

## Open questions

- Linux guest version, VM allocation, and nested virtualization support.
- CI provider configuration and runner access.
- Representative telemetry capture format and coverage.
- Which roles require real hardware, system VMs, or simulated device interfaces.
