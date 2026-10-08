# VersionGuard results: dev split

> Development results are for checking the pipeline; the registered decision rule applies to test results.

## Run coverage

| Model | Tasks recorded | Tasks with all six cells | Cells recorded | Expected cells |
|---|---|---|---|---|
| `qwen2.5:7b-instruct` | 20 | 20 | 120 | 120 |

## 1. Tests passed, by condition

| Model | 1 Task only | 2 Version | 3 Lookup | 4 Correct docs | 5 Repair, log only | 6 Repair, log + docs |
|---|---|---|---|---|---|---|
| `qwen2.5:7b-instruct` | 55.0% (11/20) | 50.0% (10/20) | 35.0% (7/20) | 50.0% (5/10) | 50.0% (10/20) | 50.0% (10/20) |

Conditions 5 and 6 are the result after one repair round: tasks that already passed in condition 2 keep their pass, tasks that failed get one retry. Condition 4 only covers tasks whose reference APIs could be matched to documentation.

## 2. Paired comparisons

| Model | Comparison | Tasks | Pass rate | Difference, points [95% CI] | p | Tasks gained / lost | Verdict |
|---|---|---|---|---|---|---|---|
| `qwen2.5:7b-instruct` | Lookup vs version only | 20 | 50.0% -> 35.0% | -15.0 [-30.0, +0.0] | 0.250 | +0 / -3 | no effect detected |
| `qwen2.5:7b-instruct` | Repair with docs vs repair with log only | 20 | 50.0% -> 50.0% | +0.0 [+0.0, +0.0] | 1.000 | +0 / -0 | no effect detected |
| `qwen2.5:7b-instruct` | Version only vs task only | 20 | 55.0% -> 50.0% | -5.0 [-20.0, +10.0] | 1.000 | +1 / -2 | no effect detected |
| `qwen2.5:7b-instruct` | Correct docs vs lookup (room left in the lookup) | 10 | 40.0% -> 50.0% | +10.0 [+0.0, +30.0] | 1.000 | +1 / -0 | no effect detected |
| `qwen2.5:7b-instruct` | One repair round vs no repair | 20 | 50.0% -> 50.0% | +0.0 [+0.0, +0.0] | 1.000 | +0 / -0 | no effect detected |

Verdicts in bold apply the rule fixed in `experiment/PROTOCOL.md`: *useful* needs a gain of at least 10 points and a 95% interval above zero. The other rows are descriptive.

## 3. Did the lookup find the right documentation?

| Model | Lookup found a reference API | Pass rate when found | Pass rate when missed | Tasks with no oracle |
|---|---|---|---|---|
| `qwen2.5:7b-instruct` | 8/10 | 50.0% (8 tasks) | 0.0% (2 tasks) | 10 |

The lookup is the same for every model (it is computed once and cached), so the first column is identical across models. A high pass rate when found and a low one when missed points at retrieval; a low pass rate even when found points at the model not using the documentation.

## 4. Why answers failed

| Model | Condition | Failed | Wrong result | API missing | Wrong arguments | Other error | No code | Timeout |
|---|---|---|---|---|---|---|---|---|
| `qwen2.5:7b-instruct` | 1 Task only | 9 | 6 | 2 | 0 | 1 | 0 | 0 |
| `qwen2.5:7b-instruct` | 2 Version | 10 | 5 | 2 | 0 | 3 | 0 | 0 |
| `qwen2.5:7b-instruct` | 3 Lookup | 13 | 9 | 2 | 0 | 2 | 0 | 0 |
| `qwen2.5:7b-instruct` | 4 Correct docs | 5 | 5 | 0 | 0 | 0 | 0 | 0 |
| `qwen2.5:7b-instruct` | 5 Repair, log only | 10 | 5 | 2 | 1 | 2 | 0 | 0 |
| `qwen2.5:7b-instruct` | 6 Repair, log + docs | 10 | 6 | 1 | 0 | 3 | 0 | 0 |

Categories are assigned automatically from the error: *API missing* is an AttributeError or ImportError, *wrong arguments* is a TypeError about the call's arguments, *wrong result* is a failed assertion.

## 5. The repair round

| Model | Failed first attempt (condition 2) | Fixed with log only | Fixed with log + docs |
|---|---|---|---|
| `qwen2.5:7b-instruct` | 10 | 0/10 | 0/10 |

## 6. By kind of library change

| Model | Kind of change | Tasks | 2 Version | 3 Lookup | 6 Repair, log + docs |
|---|---|---|---|---|---|
| `qwen2.5:7b-instruct` | argument or attribute change | 7 | 57.1% | 42.9% | 57.1% |
| `qwen2.5:7b-instruct` | breaking change | 4 | 50.0% | 25.0% | 50.0% |
| `qwen2.5:7b-instruct` | new func/method/class | 4 | 50.0% | 25.0% | 50.0% |
| `qwen2.5:7b-instruct` | deprecation | 2 | 100.0% | 100.0% | 100.0% |
| `qwen2.5:7b-instruct` | output change | 2 | 0.0% | 0.0% | 0.0% |
| `qwen2.5:7b-instruct` | output behaviour | 1 | 0.0% | 0.0% | 0.0% |

Groups this small are for spotting patterns, not for conclusions.

## 7. How these numbers were produced

| Model | Model digest | Ollama | Laptop | Temp. | Seed | Context | Lookup cache | Executor |
|---|---|---|---|---|---|---|---|---|
| `qwen2.5:7b-instruct` | 845dbda0ea48 | 0.35.0 | Windows AMD64 | 0.0 | 42 | 4096 | a721503561a6 | docker |

Each model ran on one laptop. Speed is not compared across laptops.

## 8. Model time and tokens on this laptop

| Model | Condition | Generated answers | Median seconds | Model minutes | Input tokens | Output tokens |
|---|---|---|---|---|---|---|
| `qwen2.5:7b-instruct` | 1 Task only | 20 | 5.0 | 2.8 | 2665 | 1598 |
| `qwen2.5:7b-instruct` | 2 Version | 20 | 4.4 | 1.9 | 3517 | 1475 |
| `qwen2.5:7b-instruct` | 3 Lookup | 20 | 4.1 | 1.7 | 8943 | 1260 |
| `qwen2.5:7b-instruct` | 4 Correct docs | 10 | 3.4 | 0.8 | 3116 | 561 |
| `qwen2.5:7b-instruct` | 5 Repair, log only | 10 | 7.6 | 1.3 | 3387 | 1013 |
| `qwen2.5:7b-instruct` | 6 Repair, log + docs | 10 | 6.4 | 1.3 | 5596 | 982 |

Carried first-attempt passes and skipped cells do not count as model calls.

