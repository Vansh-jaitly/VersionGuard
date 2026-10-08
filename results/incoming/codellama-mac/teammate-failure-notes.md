# CodeLlama 7B failure notes (held-out test)

Inspected ten failed cells from `results/test-codellama_7b-instruct.jsonl`, covering
`wrong_result`, `api_missing`, `api_signature`, `other_error`, and `no_code` across
task-only, version, lookup, oracle, and repair conditions. Patterns below; each has
one concrete example.

## Pattern 1 — Batched SciPy calls used as if they were 2-D

Several `scipy.linalg` / `scipy.ndimage` tasks ask for batched arrays. CodeLlama
calls the unbatched API (`det(A)`, `percentile_filter(A, percentile, size)`) and
either raises `ValueError: expected square matrix` or returns the wrong shape.

**Example, task 121, task-only:** `return det(A)` on a batch of matrices. Error:
`ValueError: expected square matrix`. The same shape of mistake appears on tasks
158 (`det(matrices)`), 132, 139, and 130 (ndimage filters without axes).

## Pattern 2 — Invented keyword arguments for the pinned version

When the prompt mentions a batch dimension, the model invents `axis=` (or similar)
even if that keyword does not exist on the pinned function.

**Example, task 122, version:** `return det(A, axis=0)` →
`TypeError: det() got an unexpected keyword argument 'axis'`.
Task 134, oracle: `median_filter(A, size=size, axis=0)` → the same class of
`TypeError`.

## Pattern 3 — Lookup documentation is pasted, not used

Condition 3 often produces longer answers that import extra names from the retrieved
snippets and then fail for reasons unrelated to the original bug (NameError, sparse
`.format`, extra methods). Lookup pass rate is slightly *below* version-only
(40.0% vs 42.5%).

**Example, task 137, lookup:** imported `minimum_filter` but called
`minimum_filter1d` and `ndimage.extrema`. Error:
`NameError: name 'minimum_filter1d' is not defined`.
Task 186, lookup: the only `no_code` cell; the answer starts a real function then
drifts into unrelated `sympy.polys` imports, so the extractor finds no usable
`custom_generateInertia`.

## Pattern 4 — Memorized SymPy names that are gone or never existed

On sympy 1.11–1.13 the model uses names from other libraries or older APIs:
`sympy.partitions`, `sympy.divisible`, `sympy.jacobi(a, n)` (wrong arity).

**Example, task 202, task-only:** `return sympy.partitions(n)` →
`AttributeError: module 'sympy' has no attribute 'partitions'`.
Task 199: `sympy.divisible(n, p)` → the same missing-attribute category.
Task 201: `sympy.jacobi(a, n)` → `TypeError: jacobi takes exactly 4 arguments (2 given)`.

## Pattern 5 — Repair with the log alone does not change the call

Log-only repair fixed **0 of 23** version-only failures. The traceback is shown,
but the second attempt usually repeats the same API. Repair *with documentation*
fixed **9 of 23** and is the only comparison that meets the registered “useful” rule
(+22.5 points, 95% CI [+10.0, +35.0]).

**Example, task 185:** first attempt `return int(a.rep)` →
`AttributeError: ... no attribute 'rep'`. Repair with log still misses; repair with
docs becomes `return K.to_int(a)` and passes.

## Ten inspected cells

| Task | Library | Condition | Category | What failed |
|---:|---|---|---|---|
| 121 | scipy 1.9.2 | task_only | other_error | `det(A)` on a batch |
| 158 | scipy 1.9.1 | task_only | other_error | `det(matrices)` on a batch |
| 132 | scipy 1.9.2 | version | wrong_result | ndimage filter, no axes |
| 134 | scipy 1.9.2 | oracle | api_signature | `median_filter(..., axis=0)` |
| 122 | scipy 1.11.2 | version | api_signature | `det(A, axis=0)` |
| 137 | scipy 1.11.2 | lookup | other_error | called unimported `minimum_filter1d` |
| 186 | sympy 1.13 | lookup | no_code | answer drifted; no usable function |
| 202 | sympy 1.13 | task_only | api_missing | `sympy.partitions` |
| 201 | sympy 1.13 | task_only | api_signature | `sympy.jacobi` arity |
| 185 | sympy 1.13 | task_only | api_missing | `.rep` on a finite-field element |
