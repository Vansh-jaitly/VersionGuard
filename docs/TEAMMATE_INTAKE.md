# CodeLlama Return: Validation and Findings

Received and audited 8 October 2026 from the extracted teammate deliverable.
Actual project root was `Downloads/VersionGuard/VersionGuard/VersionGuard`.
The return was read without executing its project scripts or replacing local source.

## Acceptance and provenance

The test run is accepted as a complete independent Mac run. Strict import into
the existing mixed-model results directory was rejected because Ollama versions
differ: CodeLlama used 0.32.15, while Qwen used 0.35.0. The source protocol does
not register a particular Ollama version, and its decision rules are applied
separately within each model. The handoff did request matching 0.35.0; that
operational requirement was not met. This is recorded rather than corrected in metadata.

| Check | Outcome |
|---|---|
| Model | `codellama:7b-instruct`, digest prefix `8fdf8f752f6e` |
| Host | Darwin arm64; Python 3.12.15; task execution in pinned Docker |
| Fixed settings | Temperature 0, seed 42, context 4096, output cap 768, timeout 120s |
| Dataset, split, cache and protocol | All four hashes match; returned files also match local raw bytes |
| Returned core Python source | Matches local `versionguard/` and `experiment/` source bytes |
| Returned Qwen held-out files | Identical to existing Qwen files |
| Held-out coverage | 40 tasks, exactly 240 unique condition records |
| Actual generations | 188; 34 carried passes and 18 unavailable-oracle skips |
| Record consistency | No duplicate run IDs, inconsistent scored statuses or invalid oracle skips |
| Repair carries | Match the initial version-only passes and their candidate code |
| Recorded environment errors | Zero |
| Reference-verification log | 60 unique selected tasks reported passing; task set matches the split |
| Development | Five-task smoke, 30 records; deliberately not a complete 20-task dev evaluation |

The reference log establishes what the teammate reported; it is not a fresh
local replay of all 60 references. The intake separately replayed the nine
documentation-assisted repair gains in local pinned Docker containers.

## Independently regenerated held-out scores

| Condition | Qwen | CodeLlama |
|---|---:|---:|
| Task only | 21/40 (52.5%) | 20/40 (50.0%) |
| Version only | 18/40 (45.0%) | 17/40 (42.5%) |
| Retrieved docs | 21/40 (52.5%) | 16/40 (40.0%) |
| Reference-API docs, eligible subset | 10/22 (45.5%) | 10/22 (45.5%) |
| Repair, log only | 22/40 (55.0%) | 17/40 (42.5%) |
| Repair, log plus docs | 22/40 (55.0%) | 26/40 (65.0%) |

These side-by-side values are descriptive. Different inference runtime versions,
models and laptops prevent attributing their differences solely to model choice.
Timing is not compared across machines.

| Primary within-model comparison | Qwen | CodeLlama |
|---|---|---|
| Lookup vs version | +7.5 points, CI [-7.5, +22.5]; no effect detected | -2.5 points, CI [-20.0, +15.0]; no effect detected |
| Repair docs vs repair log | 0.0 points, CI [-7.5, +7.5]; no effect detected | +22.5 points, CI [+10.0, +35.0], permutation p=0.005; useful |

CodeLlama's repair comparison meets both registered criteria: at least +10
points and a 95% paired-bootstrap interval entirely above zero. Log-only repair
fixed 0/23 initial failures; log-plus-doc repair fixed 9/23. The repair conditions
retain the 17 original passes, giving totals of 17 and 26 passes respectively.

This supports documentation-assisted repair for CodeLlama in this study.
It does not show that first-attempt retrieval helps either model, that CodeLlama
is generally better, or that documentation helps every local model. Qwen's
inconclusive findings remain part of the conclusion.

## Independent execution replay

The saved original answers for tasks 129, 130, 131, 132, 139, 184, 185, 199 and
202 were assembled using the local unchanged parser and run against the fixed
task tests in their pinned Docker environments. All 18 recorded pass/fail outcomes
and extracted candidate programs matched: nine passing docs repairs and nine
failing log-only repairs. No model was called and original result files were not changed.

For task 185, the actual version-only attempt used `a.lift()`, the log repair
used `a.rep`, and the documentation repair used `K.to_int(a)`. The teammate's
notes describe the initial call imprecisely; their original notes are preserved,
and this account follows the raw records.

Replay corroborates these specific gains, not all 240 recorded executions,
the original generation process, or the absence of all possible confounders.

## Files and reproducible commands

- `results/incoming/codellama-mac/`: original CodeLlama test files, five-task dev
  smoke, supplied reference log/failure notes, intake audit and regenerated reports.
- `results/incoming/codellama-mac/repair-gains-replay.json`: independent execution evidence.
- `results/model-comparison/`: frozen copies of both test datasets and regenerated
  side-by-side report/CSVs. The combined report intentionally remains provisional.
- Existing Qwen files and root `results/report-test.md` remain the original Qwen study.

```powershell
.venv\Scripts\python.exe -m experiment.report --split test --model codellama:7b-instruct --results-dir results/incoming/codellama-mac --require-complete
.venv\Scripts\python.exe -m experiment.report --split test --results-dir results/model-comparison
.venv\Scripts\python.exe -m scripts.verify_returned_repairs results/incoming/codellama-mac/test-codellama_7b-instruct.jsonl --output results/incoming/codellama-mac/repair-gains-replay.json
```

The strict combined completeness check still rejects the Ollama mismatch. Do
not edit version fields, change the registered protocol, or use `--force` to
hide it. Use the standalone model reports and disclose the combined limitation.
A matched-runtime replication, if required, must be separately labeled and
preserve these original runs; it is not needed to inspect the returned findings.
