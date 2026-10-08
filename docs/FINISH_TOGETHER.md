# Final Completion Session

Current status: 8 October 2026. Core code, first-model evaluation, hosted CI,
red/green PR demonstration and submission documents are complete.

Update: the teammate return is now audited and CodeLlama's nine repair gains
independently replayed. The combined report retains its runtime mismatch.
The user deferred Codeium/Windsurf work after editor login failed; do not
restart that task until requested.

## 1. Actual Codeium/Windsurf tests

Official extension `Codeium.codeium` 1.49.2 (Marketplace title: Windsurf Plugin,
formerly Codeium) is installed in VS Code. Installation alone is not generated-test evidence.

The prepared workspace is `.tools/codeium-input/`. It contains only the two
approved research-independent inputs and `TEST_PROMPT.md`. Sign in to the
extension and send that prompt in its Chat, with both Python files included.
Keep the original response in the editor. If the extension offers an Apply
action, apply the proposed new file to `tests/test_generated_repair.py` inside
this isolated workspace. Do not apply changes to the implementation.

The coding assistant will inspect the original proposal, retain meaningful
tests, record discarded tests and reasons, run the full suite, and compare
coverage against `results/ai-tests/before-coverage.json`. Its baseline already
passed 92 tests and 2 subtests on the unchanged core source. The source revision
is `5972e34c714fc524380090e7ef684fd53210af63`. Save tool version, exact prompt,
raw response and input hashes with the reviewed tests.

The earlier Qodo-only permission does not grant arbitrary third-party access to
other files. This workspace limits the files offered to Codeium; no credentials,
benchmark answers or personal documents are included. Its service must actually
return tests before the rubric item is marked complete.

## 2. Sweep requirement

The official current plugin is [Sweep: AI Autocomplete & Coding Agent](https://plugins.jetbrains.com/plugin/26860-sweep-ai-autocomplete--coding-agent),
published by verified vendor Sweep AI. No JetBrains installation was found in
the two common installation directories checked. The former GitHub app route
has not been established. Ask the assessor whether current Sweep in JetBrains
or another supported issue-to-PR tool satisfies the older rubric wording.
Do not claim that the plugin reproduces legacy GitHub automation without evidence.

If accepted and accessible, use the real tool on a small non-benchmark change,
review the diff, open a PR and capture its hosted checks. Save actual tool
provenance. Installing a plugin or opening an issue alone does not complete this.

## 3. Five-minute demonstration and rehearsal

1. Explain the problem with `np.asscalar` and the pinned version.
2. Show the saved vector RAG answer and retrieved sources; disclose irrelevant retrieval.
3. Open the real failed PR run and its VG001 annotation.
4. Show Qwen's posted `np.isscalar` proposal and its independent test failure.
5. Show the reviewed `array.item()` correction, passing Docker checks and green CI.
6. Explain Qwen's 45% version baseline, 52.5% lookup and 55% repairs, and why
   the uncertainty does not establish documentation benefit.
7. Show actual generated-test evidence once available, then explain tool gaps honestly.

Student rehearsal and understanding must be demonstrated personally. The
assistant cannot certify them by generating this checklist.

## 4. Teammate result intake

CodeLlama's complete held-out run, smoke test and reference log are received.
Standalone validation passes; the combined report is provisional due to Ollama
0.32.15 versus 0.35.0. See `docs/TEAMMATE_INTAKE.md`. Original runs are preserved;
no extra Qwen run is needed.
