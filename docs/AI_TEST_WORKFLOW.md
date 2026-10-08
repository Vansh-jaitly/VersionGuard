# Named-Tool Test Generation and Coverage Evidence

This rubric item requires the actual accepted CodiumAI/Qodo or Codeium tool.
Existing project-authored tests and tests written by this coding assistant do
not establish that requirement. Qodo/Codeium was not installed in the inspected
VS Code extension list on 8 October 2026; CLI availability is being checked.

## Comparable measurement

1. Fix the source revision; record source hashes/commit and tool version.
2. Run existing tests and save coverage before generation.
3. Ask the accepted tool for tests, save its raw output and prompt.
4. Review the output for meaningful behavior rather than assertions copied from
   implementation internals. Put retained tests in `tests/test_generated_*.py`.
5. Record every retained/discarded test with its reason. Fix implementation bugs
   separately; re-establish a baseline if source changes.
6. Run the same full suite/coverage scope with retained tests and save after output.
7. Compare with `scripts.coverage_compare`, retaining tool provenance alongside it.

## Prompt ready for the accepted tool

Generate focused pytest/unittest tests for `versionguard/codeparse.py`,
`versionguard/repair.py`, `versionguard/store.py` and `versionguard/check.py`.
Read existing tests first. Target untested behavior: malformed/truncated model
answers, traceback sanitization without expected-value leakage, retrieval
ranking/duplicate API paths, and protective API probes. Use controlled fake
modules/mocks. Do not access Ollama/network or run generated code on the host.
Do not change implementation files. Provide complete test files and explain
which observable behavior each test verifies. Avoid duplicating existing tests.

## Evidence record

| Field | Value to record |
|---|---|
| Tool/version | Actual accepted tool |
| Source revision/hash set | Identical core source for both runs |
| Prompt/raw output | Saved artifact paths |
| Proposed / kept / discarded tests | Actual reviewed counts |
| Rejection reasons | Duplicates, invalid assumptions, nondeterminism or lack of value |
| Before/after coverage and logs | Equivalent interpreter, scope and command |
| Tool-authorship status | Verified only after real generation |

No tool-generated-test claim is currently made by this document.
