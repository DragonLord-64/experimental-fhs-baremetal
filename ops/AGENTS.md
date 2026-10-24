# Task workflow

Use one implementation pass followed by the user's review. The user requested
this policy on 2026-10-24; do not require or spawn an independent review agent.

The implementation worker reads the original task and applicable instructions,
inspects relevant source, establishes useful baseline evidence, implements the
change and runs checks appropriate to the requirement. Add meaningful tests when
they expose a risk or regression; do not weaken tests or hide failures. Preserve
user edits, credentials and the host safety rules.

Report what changed, actual validation and remaining limits. Make the completed
change reviewable. Once requested work is complete and appropriate checks pass,
commit/merge and push it to the private experimental origin without asking again.
Preserve unrelated user edits; never push to official SKA upstream. The user
provides the review step. Tests passing alone do not prove hardware behavior or
untested integration boundaries.

For automated runs, [agent-pipeline](agent-pipeline/README.md) launches one worker
and runs configured acceptance commands before marking implementation complete
for user review. Pause/redirect/resume may restart an interrupted worker. Do not
restart unrelated preserved runs merely because this workflow changed.
