# Integration verification

Verified locally on Windows, Python 3.12.3, 2026-10-08.

| Check | Result |
|---|---|
| Full suite in project virtual environment | 89 passed, 2 subtests passed |
| Ruff | Passed |
| Configured core coverage | 69%; integration JSON saved separately |
| Workflow YAML | Parsed; triggers and read-only permissions checked |
| Fixture pipeline | All 36 condition cells; complete report generated |
| Guard demo, NumPy 1.26.4 | Removed `numpy.asscalar` fails with VG001; corrected code passes |
| Application guard | No errors; optional lookup/client imports produce warnings in the minimal environment |
| Result import | Existing Qwen test run validated in preview mode; files unchanged |
| Teammate package | File hashes verified; frozen Qwen test report reproduced exactly after fresh-directory extraction |

PR integration tests cover saved previews without posting, rejection of a
changed PR head, explicit posting, updating only an owned marked comment,
path traversal rejection and containment of model Markdown in comment fences.
GitHub calls in these tests are mocked. No live PR comment or hosted Actions
run has been performed. Package verification is local; no archive has been
sent externally.

The earlier `coverage-baseline.json` remains untouched for future Qodo
comparisons. `coverage-integration.json` records this stage. Coverage targets
the core `versionguard/` and `experiment/` modules; helper scripts are exercised
by integration tests but are not included in that percentage.

Completed Qwen evaluation records, metadata, dataset, split, lookup cache and
protocol were preserved. No model benchmark cells were rerun in this stage.
