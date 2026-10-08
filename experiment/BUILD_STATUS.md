# Build status and handoff

Updated 2026-10-08. The core implementation and first model evaluation are
complete. CI and local PR repair integration are implemented; the project still
needs the second model and hosted integration/demo evidence.

## Completed evaluation

Model: `qwen2.5:7b-instruct`, digest prefix `845dbda0ea48`, Ollama 0.35.0,
Windows AMD64, Docker. Temperature 0, seed 42, context 4096, output limit 768,
execution timeout 120 seconds. Development took 12.2 minutes; test took 26.2.

| Split | Tasks | Condition records | Status |
|---|---:|---:|---|
| Development | 20 | 120 | Complete |
| Held-out test | 40 | 240 | Complete |

All 240 expected test keys were verified exactly once, with no environment
errors. Eighteen oracle cells are explicitly skipped because reference APIs
could not be matched to documentation. Already-passing version attempts are
carried forward into repair conditions without another model call.

| Held-out condition | Passed |
|---|---:|
| Task only | 21/40 (52.5%) |
| Version only | 18/40 (45.0%) |
| Lookup | 21/40 (52.5%) |
| Oracle | 10/22 (45.5%) |
| Repair, log only | 22/40 (55.0%) |
| Repair, log plus docs | 22/40 (55.0%) |

Neither primary comparison meets the registered rule. Lookup gains 7.5 points
over version only, with a 95% interval [-7.5, +22.5]. Documentation adds 0 points
to repair, with a 95% interval [-7.5, +7.5]. Each repair method fixes 4 of 22
failed version-only attempts, but they fix different tasks. These data support
an honest negative/inconclusive primary result, not a claim of demonstrated
documentation benefit.

Evidence lives in `results/report-test.md`, `results/report-dev.md`, model JSONL
files and matching metadata. CSV exports include pass counts, paired
comparisons and failure details. Keep the completed evaluation data, split,
protocol and retrieval cache fixed. Future retrieval or prompt changes need a
separate experiment; do not overwrite these results to improve the score.

## Core implementation and safeguards

- Three commands remain the interface: `versionguard.ask`, `versionguard.check`
  and `experiment.run`.
- Bot lookup uses pinned documentation; standalone repair accepts paired
  `--code` and `--error-log`, preserves guard diagnostics and sanitizes
  assertion/traceback feedback.
- Bot proposals include static guard findings when the installed library
  matches the requested version. A different version reports `not_checked`.
  The bot proposes code without modifying or executing the supplied source.
- Real evaluations require Docker and a complete usable preparation cache.
  Dataset/split hashes and cache environment keys are checked before runs.
- Resume locks the model digest, Ollama version, generation settings, timeout,
  protocol and dataset/split/cache identity; earlier metadata without new keys
  remains readable.
- Preparation saves failed reference records and replaces its cache atomically.
- Reports reject duplicate cells and incompatible result metadata, flag partial
  runs, support model selection and can require complete coverage. Timing
  excludes carried passes and skipped cells.
- Guard regressions cover protective `hasattr`/`getattr` branches, owner
  matching, OR conditions, truthy defaults and GitHub annotation escaping.
- Ollama HTTP errors expose useful response details rather than an unexplained
  HTTP 500.

## Verification and independent repair demonstration

On Python 3.12: `79 passed, 2 subtests passed`; Ruff passes. Coverage is 69%
overall (guard 85%, report 94%, parsing 95%). The machine-readable baseline is
`results/coverage-baseline.json`; it is a baseline for future generated tests,
not a measured Qodo improvement.

The standalone Qwen demonstration initially proposed invalid `np.item(array)`.
That answer is preserved in `results/repair-demo-initial.json`. Standalone
repair retrieval now uses the question and source instead of traceback
boilerplate. With a clarified question the new proposal uses `array.item()`.
Both proposals were tested in the pinned NumPy 1.25.0 Docker image: the first
fails with AttributeError and the second passes integer, float, scalar,
one-element multidimensional and multiple-element rejection checks. Evidence:
`results/repair-demo.json` and `results/repair-demo-verification.json`.

This is one illustrative repair example with a revised question, not a repair
success rate or another benchmark result. Host NumPy is 1.26.4, so local static
checking honestly reports `not_checked` for this pinned 1.25.0 example.

## Next stage

Integration stage verification: 89 tests and 2 subtests pass, lint passes,
core coverage is 69%, the 36-cell fixture pipeline and pinned guard demo pass,
and the delivery archive reproduces the frozen Qwen report from a fresh
directory. See `results/integration-validation.md`. PR API behavior is tested
with mocks; hosted GitHub evidence remains pending.

1. Share the source, fixed split and retrieval cache with the teammate. No Git
   remote or commits are configured in this checkout yet, so nothing has been
   published or sent. The benchmark data can be fetched independently.
2. The teammate verifies preparation on their laptop and runs the installed
   `codellama:7b-instruct` model there, using the same settings. This is the
   selected approximately same-size, code-focused comparison to Qwen. Use
   development tasks for the initial smoke check, then run the held-out test
   once. Return model JSONL and metadata and merge them through the report
   command. Do not rerun Qwen under its `qwen2.5:7b` alias: both tags identify
   the same local model.
3. `.github/workflows/ci.yml` now covers lint, tests, coverage, the fixture
   pipeline, a NumPy guard demo and changed application files. Verify a hosted
   PR and capture the removed-API failure and corrected pass. No live Actions
   run exists yet.
4. `scripts.pr_repair` now creates a comment preview via the existing bot
   command from a PR file at a fixed commit. Explicit `--post` checks that head
   again and creates/updates only the authenticated user's VersionGuard
   comment. PR source is not checked out or executed. Live posting is pending.
5. Generate and review Qodo tests, then compare coverage against the saved
   baseline. Record kept/discarded counts and reasons. Current tests were not
   produced by Qodo and should not be presented as such.
6. Attempt the Sweep integration after the repository is hosted; save actual
   results or the installation limitation. Collect screenshots, inspect failure
   examples and prepare the report/slides around the measured findings.

The user authorized implementing the next stage before teammate delivery.
`scripts.teammate_bundle` packages a curated archive with checksums, and
`scripts.import_results` validates complete incoming test data against fixed
inputs/settings before copying. Cross-model reporting also checks generation
settings and Ollama versions. The original coverage baseline is preserved.
See `docs/HANDOFF.md` for the current handoff instructions.

No second model, live Actions/PR comment, Qodo or Sweep result is claimed as
completed. Nothing has been published or sent externally.
