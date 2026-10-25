# Task workflow

Use one implementation worker followed by the user's review. Do not require or
spawn a screening agent, manager agent or independent review agent for a task.
The [pipeline manager](agent-pipeline/README.md) is a small queue/lab helper.

Read the original task, nearest instructions and relevant source. Keep the goal,
allowed paths, acceptance commands and exclusions explicit. Do not expand a tiny
change into framework work, broad cleanup or infrastructure validation. Record
newly found unrelated problems for later work instead of fixing them incidentally.

Choose checks by changed behavior:

- Docs/wiki: inspect content and affected links; no model, container or lab runs.
- Controller/tooling: fast syntax checks and its focused fake-worker tests.
- Ansible: lint/syntax for the changed role or playbook, then its relevant fixture.
- Chart/importer/runtime: focused contracts and the existing real chart/importer
  lab acceptance when runtime behavior changes. Name context `fhs-test` explicitly.

Run each acceptance command once for the final change. In automated tasks the
controller runs configured checks; the worker uses extra checks only to diagnose
a failure or cover a specific behavior those commands miss, explaining why.
Broaden or repeat only for new changes, failures or unresolved concerns. Do not
add tests that merely mirror implementation, new test frameworks, whole-cluster
lifecycle tests, repeated full suites or benchmarks for a small edit. Never weaken
existing checks or hide failures to meet the budget. Report scope/budget blockers.

Preserve user edits, credentials and host safety. Report changes, observed
validation and limits. Once requested work is complete and appropriate checks
pass, commit/merge and push only the private experimental origin without asking
again. The caller publishes dispatched work; workers do not publish independently.
Tests passing do not prove hardware behavior or untested integration boundaries.

Task intake and scouting are local CLI operations; they do not create GitHub
issues for every small slice. Use GitHub issues for actionable feature scope and
acceptance. Do not restart unrelated preserved runs when changing this workflow.
