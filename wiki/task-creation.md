# Creating tasks and acceptance

Confirmed user feedback, 2026-10-25: finish the requested change and use focused
tests. Task creation must not turn a practical fix into an extensive test-harness
project. The NetBox discovery task spent about 28 minutes in implementation before
its first acceptance run; the user redirected it to finish with focused checks.
This is a lesson about scope, not a claim that the changes passed.

## Task contents

Write a short goal, relevant evidence, allowed paths, explicit exclusions and a
finite acceptance list. Describe the user-visible behavior to deliver. Separate
required behavior from suggested future work; do not promote suggestions into
requirements. Preserve the user's latest corrections when bundling a discussion.

Reference representative inputs, including user screenshots. Keep originals
private when they contain internal identifiers. Use a small sanitized fixture
that preserves the relevant structure and relationships; do not recreate an
entire environment from every detail in a photo.

Use this outline:

```text
Goal: the concrete behavior the user needs.
Evidence: current source and representative failing input.
Scope: paths and behavior that may change; explicit exclusions.
Acceptance:
- the reported case produces the expected result;
- a relevant conflict/failure preserves existing data;
- repeat execution is unchanged, when reconciliation is involved;
- one focused integration check if an external runtime boundary changes.
Checks: exact existing commands, owner and realistic budget.
Limits: what these checks cannot establish.
```

## Choose acceptance by changed behavior

| Change | Useful minimum |
|---|---|
| Documentation | Inspect content, affected links and commands. |
| Parser or discovery correction | Representative actual input plus a relevant missing/ambiguous case. |
| Ansible wiring/configuration | Syntax and the focused real-task fixture. |
| NetBox reconciliation | Changed object behavior, conflict preservation and repeat-import idempotency; one small native test on the existing delivered chart. |

Reuse existing tests, helpers, credentials and lab services. A new focused fixture
or a short extension to an existing check is usually enough. Explain a new harness
only when an existing entrypoint cannot verify the changed boundary; building it
must not dominate delivering the fix.

Acceptance must prove the requested behavior, not every adjacent system:

- Do not repeat full asset lifecycles, every failure permutation, all preview
  modes and plugin rendering in a new harness when existing coverage already
  establishes them. Test a mode directly when the change affects its behavior.
- Do not add cluster lifecycle tests, benchmarks, broad infrastructure checks,
  extra frameworks or unrelated regression work to a bounded change.
- Keep one representative native check when importer/runtime behavior changes.
  A mock or screenshot cannot prove the NetBox API accepts the resulting objects;
  this does not require deploying the whole stack or recreating the lab.
- Keep conflict and data-preservation checks tied to the actual risk. Focused
  acceptance is not permission to ignore failures, weaken protections or claim
  unobserved success.

The controller runs configured acceptance once for the final change. The worker
adds a check only for a specific uncovered behavior or to diagnose a failure.
Repeat checks only after changes or an unresolved failure justify it.

## Finish and report

Once the requested behavior and focused acceptance are satisfied, stop adding
coverage and hand back the result. Record unrelated findings separately. If test
infrastructure is becoming the main work, explain the cost and use the smallest
adequate existing check; a substantial new validation project needs its own scope.

Report implementation state separately from validation state. Give observed
passes, failures and limits; avoid completion percentages without a concrete
basis. When asked about delay, identify the actual current work and remaining
milestone. The user reviews the result.

[Worker rules](../ops/AGENTS.md),
[pipeline intake and controls](../ops/agent-pipeline/README.md).
