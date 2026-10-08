# VersionGuard results: test split

## Run coverage

| Model | Tasks recorded | Tasks with all six cells | Cells recorded | Expected cells |
|---|---|---|---|---|
| `qwen2.5:7b-instruct` | 40 | 40 | 240 | 240 |

## 1. Tests passed, by condition

| Model | 1 Task only | 2 Version | 3 Lookup | 4 Correct docs | 5 Repair, log only | 6 Repair, log + docs |
|---|---|---|---|---|---|---|
| `qwen2.5:7b-instruct` | 52.5% (21/40) | 45.0% (18/40) | 52.5% (21/40) | 45.5% (10/22) | 55.0% (22/40) | 55.0% (22/40) |

Conditions 5 and 6 are the result after one repair round: tasks that already passed in condition 2 keep their pass, tasks that failed get one retry. Condition 4 only covers tasks whose reference APIs could be matched to documentation.

## 2. Paired comparisons

| Model | Comparison | Tasks | Pass rate | Difference, points [95% CI] | p | Tasks gained / lost | Verdict |
|---|---|---|---|---|---|---|---|
| `qwen2.5:7b-instruct` | Lookup vs version only | 40 | 45.0% -> 52.5% | +7.5 [-7.5, +22.5] | 0.510 | +6 / -3 | **no effect detected** |
| `qwen2.5:7b-instruct` | Repair with docs vs repair with log only | 40 | 55.0% -> 55.0% | +0.0 [-7.5, +7.5] | 1.000 | +1 / -1 | **no effect detected** |
| `qwen2.5:7b-instruct` | Version only vs task only | 40 | 52.5% -> 45.0% | -7.5 [-20.0, +5.0] | 0.457 | +2 / -5 | no effect detected |
| `qwen2.5:7b-instruct` | Correct docs vs lookup (room left in the lookup) | 22 | 50.0% -> 45.5% | -4.5 [-13.6, +0.0] | 1.000 | +0 / -1 | no effect detected |
| `qwen2.5:7b-instruct` | One repair round vs no repair | 40 | 45.0% -> 55.0% | +10.0 [+2.5, +20.0] | 0.126 | +4 / -0 | useful |

Verdicts in bold apply the rule fixed in `experiment/PROTOCOL.md`: *useful* needs a gain of at least 10 points and a 95% interval above zero. The other rows are descriptive.

## 3. Did the lookup find the right documentation?

| Model | Lookup found a reference API | Pass rate when found | Pass rate when missed | Tasks with no oracle |
|---|---|---|---|---|
| `qwen2.5:7b-instruct` | 19/22 | 42.1% (19 tasks) | 100.0% (3 tasks) | 18 |

The lookup is the same for every model (it is computed once and cached), so the first column is identical across models. A high pass rate when found and a low one when missed points at retrieval; a low pass rate even when found points at the model not using the documentation.

## 4. Why answers failed

| Model | Condition | Failed | Wrong result | API missing | Wrong arguments | Other error | No code | Timeout |
|---|---|---|---|---|---|---|---|---|
| `qwen2.5:7b-instruct` | 1 Task only | 19 | 8 | 4 | 0 | 6 | 1 | 0 |
| `qwen2.5:7b-instruct` | 2 Version | 22 | 10 | 6 | 0 | 6 | 0 | 0 |
| `qwen2.5:7b-instruct` | 3 Lookup | 19 | 13 | 2 | 0 | 4 | 0 | 0 |
| `qwen2.5:7b-instruct` | 4 Correct docs | 12 | 10 | 1 | 0 | 1 | 0 | 0 |
| `qwen2.5:7b-instruct` | 5 Repair, log only | 18 | 10 | 3 | 0 | 5 | 0 | 0 |
| `qwen2.5:7b-instruct` | 6 Repair, log + docs | 18 | 8 | 3 | 1 | 6 | 0 | 0 |

Categories are assigned automatically from the error: *API missing* is an AttributeError or ImportError, *wrong arguments* is a TypeError about the call's arguments, *wrong result* is a failed assertion.

## 5. The repair round

| Model | Failed first attempt (condition 2) | Fixed with log only | Fixed with log + docs |
|---|---|---|---|
| `qwen2.5:7b-instruct` | 22 | 4/22 | 4/22 |

## 6. By kind of library change

| Model | Kind of change | Tasks | 2 Version | 3 Lookup | 6 Repair, log + docs |
|---|---|---|---|---|---|
| `qwen2.5:7b-instruct` | argument or attribute change | 15 | 40.0% | 33.3% | 40.0% |
| `qwen2.5:7b-instruct` | new func/method/class | 10 | 30.0% | 50.0% | 50.0% |
| `qwen2.5:7b-instruct` | breaking change | 7 | 57.1% | 100.0% | 85.7% |
| `qwen2.5:7b-instruct` | deprecation | 4 | 100.0% | 100.0% | 100.0% |
| `qwen2.5:7b-instruct` | argument change | 1 | 0.0% | 0.0% | 0.0% |
| `qwen2.5:7b-instruct` | name change | 1 | 0.0% | 0.0% | 0.0% |
| `qwen2.5:7b-instruct` | other library or new feature | 1 | 0.0% | 0.0% | 0.0% |
| `qwen2.5:7b-instruct` | output change | 1 | 100.0% | 0.0% | 100.0% |

Groups this small are for spotting patterns, not for conclusions.

## 7. How these numbers were produced

| Model | Model digest | Ollama | Laptop | Temp. | Seed | Context | Lookup cache | Executor |
|---|---|---|---|---|---|---|---|---|
| `qwen2.5:7b-instruct` | 845dbda0ea48 | 0.35.0 | Windows AMD64 | 0.0 | 42 | 4096 | a721503561a6 | docker |

Each model ran on one laptop. Speed is not compared across laptops.

## 8. Model time and tokens on this laptop

| Model | Condition | Generated answers | Median seconds | Model minutes | Input tokens | Output tokens |
|---|---|---|---|---|---|---|
| `qwen2.5:7b-instruct` | 1 Task only | 40 | 5.5 | 4.9 | 5592 | 3827 |
| `qwen2.5:7b-instruct` | 2 Version | 40 | 4.4 | 4.0 | 7293 | 3196 |
| `qwen2.5:7b-instruct` | 3 Lookup | 40 | 3.9 | 4.1 | 18307 | 3079 |
| `qwen2.5:7b-instruct` | 4 Correct docs | 22 | 3.6 | 1.6 | 7395 | 1255 |
| `qwen2.5:7b-instruct` | 5 Repair, log only | 22 | 6.3 | 3.2 | 8238 | 2401 |
| `qwen2.5:7b-instruct` | 6 Repair, log + docs | 22 | 6.2 | 3.3 | 14049 | 2462 |

Carried first-attempt passes and skipped cells do not count as model calls.

