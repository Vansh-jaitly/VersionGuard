# Experiment protocol

Written before any model was run on the test split. If this file changes, the
change and its reason go in the commit message, and every results file records
the hash of the version it was produced under.

## Research question

Does looking up documentation for the **pinned** library version make code
written by a small local model pass more tests than the model alone, both on
the first attempt and when repairing a failed attempt?

## Data

GitChameleon 2.0: Python tasks, each tied to one library version, each with a
test and a reference solution. The tasks used, and the dev/test split, are in
`experiment/splits/split.json` together with the dataset hash and the seed.

- **dev** is for building and tuning (prompts, lookup settings).
- **test** is run once per model, after everything is fixed.
- A pinned version that has no prebuilt package for the task's Python version
  is left out when the tasks are chosen (it would have to be compiled from
  source on every laptop). The versions left out and the number of tasks this
  removes are recorded in `split.json`.
- A task whose reference solution does not pass in our environment is dropped
  before any model sees it (`experiment.prepare`).

## Conditions

Same system message, same layout, same documentation budget in characters.
Only the evidence shown changes.

| # | Name | The model is given |
|---|---|---|
| 1 | `task_only` | the task |
| 2 | `version` | the task and the pinned versions |
| 3 | `lookup` | condition 2 plus the top-k documentation entries found by the lookup |
| 4 | `oracle` | condition 2 plus the documentation of the APIs the reference solution calls |
| 5 | `repair_log` | condition 2, the failed code from condition 2, and its error log |
| 6 | `repair_docs` | condition 5 plus the same documentation entries as condition 3 |

Conditions 5 and 6 retry only tasks that failed condition 2, once. Tasks that
passed condition 2 keep their pass, so 5 and 6 are "the result after one
repair round" and can be compared with 2.

## Fixed settings

Temperature 0, seed 42, context 4096 tokens, at most 768 new tokens, top-k 3,
documentation budget 2400 characters, 120 seconds per test run. Each model
runs entirely on one laptop.

The lookup searches with the task text plus the starting code, and keeps one
entry per function name, preferring the most direct path (`numpy.any` rather
than `numpy.ndarray.any` and `numpy.matrix.any`). This was chosen on dev tasks
after the first lookups returned three copies of the same function.

## Measures

- **Primary:** share of tasks whose test passes.
- **Lookup quality:** share of tasks where a retrieved entry is one of the
  reference solution's APIs (only for tasks where those APIs can be matched).
- **Failure category**, assigned automatically from the error.
- Tokens and time per answer (reported per laptop, never compared across).

## Decision rule

Applied separately to each model, on the test split, with paired tasks:

1. **Lookup is useful** only if condition 3 beats condition 2 by at least
   10 percentage points **and** the 95% paired-bootstrap interval of the
   difference is above zero.
2. **Documentation helps repair** only if condition 6 beats condition 5 by at
   least 10 percentage points **and** the 95% interval is above zero.

Anything else is reported as "no effect detected" or "below threshold". All
other comparisons in the report are descriptive.

## What the oracle is for

Condition 4 gives the model the right documentation without any search. If 3
fails where 4 passes, the lookup missed. If 4 fails too, the model did not use
documentation it was given. That separates the two kinds of failure.

## Known limits (stated up front)

- The repair log comes from the same test that scores the answer when the
  benchmark gives no separate visible test. The model never sees the test's
  code or expected values: test frames are removed from the traceback and
  assertion messages are replaced by a fixed sentence.
- Documentation is read from the installed library (names, signatures,
  docstrings). It cannot say that something was **removed**; only the error
  log can.
- The oracle exists only when the reference solution calls a library function
  by name. Tasks solved through a method on a local variable have no oracle
  and are left out of condition 4.
- Small test split: intervals will be wide. Results apply to the models and
  libraries tested.
