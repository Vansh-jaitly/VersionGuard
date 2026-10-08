# VersionGuard results: dev split

> Development results are for checking the pipeline; the registered decision rule applies to test results.

> **Provisional report.** Coverage or provenance issues prevent treating this as a complete evaluation.

- codellama:7b-instruct: incomplete run, 90 of 120 cells missing.

## Run coverage

| Model | Tasks recorded | Tasks with all six cells | Cells recorded | Expected cells |
|---|---|---|---|---|
| `codellama:7b-instruct` | 5 | 5 | 30 | 120 |

## 1. Tests passed, by condition

| Model | 1 Task only | 2 Version | 3 Lookup | 4 Correct docs | 5 Repair, log only | 6 Repair, log + docs |
|---|---|---|---|---|---|---|
| `codellama:7b-instruct` | 80.0% (4/5) | 80.0% (4/5) | 100.0% (5/5) | 100.0% (4/4) | 80.0% (4/5) | 80.0% (4/5) |

Conditions 5 and 6 are the result after one repair round: tasks that already passed in condition 2 keep their pass, tasks that failed get one retry. Condition 4 only covers tasks whose reference APIs could be matched to documentation.

## 2. Paired comparisons

| Model | Comparison | Tasks | Pass rate | Difference, points [95% CI] | p | Tasks gained / lost | Verdict |
|---|---|---|---|---|---|---|---|
| `codellama:7b-instruct` | Lookup vs version only | 5 | 80.0% -> 100.0% | +20.0 [+0.0, +60.0] | 1.000 | +1 / -0 | no effect detected |
| `codellama:7b-instruct` | Repair with docs vs repair with log only | 5 | 80.0% -> 80.0% | +0.0 [+0.0, +0.0] | 1.000 | +0 / -0 | no effect detected |
| `codellama:7b-instruct` | Version only vs task only | 5 | 80.0% -> 80.0% | +0.0 [+0.0, +0.0] | 1.000 | +0 / -0 | no effect detected |
| `codellama:7b-instruct` | Correct docs vs lookup (room left in the lookup) | 4 | 100.0% -> 100.0% | +0.0 [+0.0, +0.0] | 1.000 | +0 / -0 | no effect detected |
| `codellama:7b-instruct` | One repair round vs no repair | 5 | 80.0% -> 80.0% | +0.0 [+0.0, +0.0] | 1.000 | +0 / -0 | no effect detected |

Verdicts in bold apply the rule fixed in `experiment/PROTOCOL.md`: *useful* needs a gain of at least 10 points and a 95% interval above zero. The other rows are descriptive.

## 3. Did the lookup find the right documentation?

| Model | Lookup found a reference API | Pass rate when found | Pass rate when missed | Tasks with no oracle |
|---|---|---|---|---|
| `codellama:7b-instruct` | 4/4 | 100.0% (4 tasks) | n/a | 1 |

The lookup is the same for every model (it is computed once and cached), so the first column is identical across models. A high pass rate when found and a low one when missed points at retrieval; a low pass rate even when found points at the model not using the documentation.

## 4. Why answers failed

| Model | Condition | Failed | Wrong result | API missing | Wrong arguments | Other error | No code | Timeout |
|---|---|---|---|---|---|---|---|---|
| `codellama:7b-instruct` | 1 Task only | 1 | 1 | 0 | 0 | 0 | 0 | 0 |
| `codellama:7b-instruct` | 2 Version | 1 | 0 | 0 | 0 | 1 | 0 | 0 |
| `codellama:7b-instruct` | 3 Lookup | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `codellama:7b-instruct` | 4 Correct docs | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `codellama:7b-instruct` | 5 Repair, log only | 1 | 0 | 0 | 0 | 1 | 0 | 0 |
| `codellama:7b-instruct` | 6 Repair, log + docs | 1 | 0 | 0 | 0 | 1 | 0 | 0 |

Categories are assigned automatically from the error: *API missing* is an AttributeError or ImportError, *wrong arguments* is a TypeError about the call's arguments, *wrong result* is a failed assertion.

## 5. The repair round

| Model | Failed first attempt (condition 2) | Fixed with log only | Fixed with log + docs |
|---|---|---|---|
| `codellama:7b-instruct` | 1 | 0/1 | 0/1 |

## 6. By kind of library change

| Model | Kind of change | Tasks | 2 Version | 3 Lookup | 6 Repair, log + docs |
|---|---|---|---|---|---|
| `codellama:7b-instruct` | argument or attribute change | 2 | 100.0% | 100.0% | 100.0% |
| `codellama:7b-instruct` | deprecation | 2 | 100.0% | 100.0% | 100.0% |
| `codellama:7b-instruct` | output change | 1 | 0.0% | 100.0% | 0.0% |

Groups this small are for spotting patterns, not for conclusions.

## 7. How these numbers were produced

| Model | Model digest | Ollama | Laptop | Temp. | Seed | Context | Lookup cache | Executor |
|---|---|---|---|---|---|---|---|---|
| `codellama:7b-instruct` | 8fdf8f752f6e | 0.32.15 | Darwin arm64 | 0.0 | 42 | 4096 | a721503561a6 | docker |

Each model ran on one laptop. Speed is not compared across laptops.

## 8. Model time and tokens on this laptop

| Model | Condition | Generated answers | Median seconds | Model minutes | Input tokens | Output tokens |
|---|---|---|---|---|---|---|
| `codellama:7b-instruct` | 1 Task only | 5 | 10.5 | 0.8 | 684 | 1231 |
| `codellama:7b-instruct` | 2 Version | 5 | 8.9 | 0.8 | 920 | 1334 |
| `codellama:7b-instruct` | 3 Lookup | 5 | 11.4 | 1.1 | 3078 | 1623 |
| `codellama:7b-instruct` | 4 Correct docs | 4 | 10.7 | 0.7 | 1350 | 1265 |
| `codellama:7b-instruct` | 5 Repair, log only | 1 | 10.4 | 0.2 | 430 | 267 |
| `codellama:7b-instruct` | 6 Repair, log + docs | 1 | 11.3 | 0.2 | 949 | 273 |

Carried first-attempt passes and skipped cells do not count as model calls.

