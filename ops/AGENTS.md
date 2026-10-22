# Task workflow

One primary agent coordinates the task and may spawn sub-agents. Use four stages and three workers: the first screens and establishes tests, the second implements, and the third independently reviews the result.

## 1. Screen

The first worker reads the original task and applicable instructions, then quickly inspects relevant code, docs, and tests. Produce a short handoff containing:

- Original task and intended outcome, preserving material wording.
- Acceptance criteria, constraints, and unresolved questions.
- Relevant paths and code behavior, with source references.
- Existing tests, dependencies, and practical test commands.

Include only useful context. Distinguish facts from assumptions. Omit unrelated repo material and secrets; do not filter out constraints or evidence that challenges the proposed solution.

## 2. Establish tests

The same worker runs relevant existing checks to establish the baseline, then adds or adjusts meaningful tests for the requested behavior where appropriate. Record commands, results, pre-existing failures, and environment limitations. Where practical, demonstrate that new tests expose the problem before implementation. Do not alter production behavior at this stage or add artificial tests merely to satisfy the process.

Pass the original task, screening handoff, acceptance criteria, tests, and baseline evidence to a fresh implementation worker. Use a fresh context rather than inheriting the whole conversation; include applicable instructions and references explicitly.

## 3. Implement

The second worker reads the handoff and relevant source, implements the change, and runs the appropriate tests. Meet the actual requirement, not just the assertions. Do not weaken tests or hide failures to obtain a pass. Flag flawed tests for correction with reasons. Report changes, test evidence, and remaining limitations to the primary agent.

## 4. Review the intent

A fresh third worker receives the original task, acceptance criteria, concise source context, final diff, and test evidence. Independently check whether the user's goal and meaning are met. Look for missing behavior, misleading passes, unjustified scope, regressions, and contradictions between code and docs. Inspect source and run focused checks when needed. Report findings with locations and severity, or state that no issues were found and identify unverified areas.

The primary agent resolves findings through the relevant worker, obtains renewed review for material fixes, and reports the outcome with evidence. Do not declare success solely because tests pass. Preserve user changes and obey root safety and repository boundaries throughout.

This is the agent work process. CI runner provisioning and automatic issue dispatch are separate work and are not implemented by this document.
