# VersionGuard: Technical Status Report

**Audience:** Senior engineering review  
**Date:** 8 October 2026, Asia/Calcutta  
**Scope:** Current local implementation, completed Qwen evaluation, integration
verification, teammate handoff and remaining delivery work.

## 1. Engineering assessment

VersionGuard is a working CLI research prototype with a complete first-model
evaluation and implemented integration tooling. The core build phase is
complete. The project is currently at cross-machine and hosted-integration
validation, rather than final delivery or production readiness.

The application can retrieve documentation for a pinned library version,
propose code or repairs using local Ollama, flag selected invalid library calls,
execute benchmark answers in pinned Docker environments, and produce paired
statistical reports. GitHub CI and a local PR repair-comment path are written
and tested locally. A verified delivery ZIP has been produced, and the user
reports having sent the teammate work. Receipt and execution by the teammate
have not been independently verified.

The primary research claim is not established by the completed Qwen run.
Documentation lookup improves the observed pass rate by 7.5 percentage points,
but the confidence interval crosses zero and the gain is below the registered
10-point threshold. Documentation adds no aggregate gain to the repair round.
These findings must remain part of the final report even if the second model
performs better.

## 2. Delivery status

| Component | Implementation | Evidence and remaining boundary |
|---|---|---|
| Bot and pinned-version documentation lookup | Complete | Real Ollama and cached vector retrieval used |
| Static library API guard | Complete within stated limits | Tests and local NumPy failure/pass demo |
| Benchmark preparation and Docker executor | Complete | All 60 selected tasks prepared across 15 environments |
| Six-condition evaluation runner | Complete | Full Qwen dev and held-out test runs |
| Standalone repair command | Complete | Independent repaired NumPy example tested in Docker |
| Reporting and result import | Complete | Qwen validation and report reproduction; second-model import pending |
| GitHub Actions workflow | Implemented | YAML parsed and steps exercised locally; hosted run pending |
| PR repair preview/posting helper | Implemented | API behavior tested with mocks; live posting pending |
| Teammate delivery archive | Complete | 83 files checksum-verified; user reports work sent |
| CodeLlama 7B evaluation on teammate Mac | Assigned | Results not received |
| Qodo and Sweep evidence | Pending | No generated-test improvement or Sweep PR claimed |
| Final combined report and presentation | Pending | Qwen report exists; combined results and external evidence pending |

## 3. Architecture and implemented behavior

### Core command contract

| Command | Responsibility |
|---|---|
| `python -m versionguard.ask` | Version-specific generation and standalone repair |
| `python -m versionguard.check` | Static installed-version API checking |
| `python -m experiment.run` | Resumable benchmark evaluation |

Supporting commands prepare/verify environments, check laptop readiness,
produce reports, validate incoming results and package the handoff. The
integration helpers delegate to the existing core commands.

### Documentation and model service

`versionguard/apidocs.py` extracts callable names, signatures and docstrings
from installed distributions. The bot caches entries per library/version and
checks the declared version against the supplied documentation. Documentation
from another environment can be supplied explicitly.

`versionguard/store.py` supports vector lookup through Chroma and embeddings,
plus keyword lookup. The benchmark uses a frozen retrieval cache so every model
gets the same retrieved evidence. The selected lookup keeps one entry per
function name and prefers direct API paths. Standalone repair lookup uses the
question and source code; error logs still reach the model but do not dominate
the search query.

`versionguard/llm.py` uses LangChain's Ollama client where installed, with a
direct local HTTP fallback using the same generation settings. The completed
Qwen runs used the fallback. HTTP error responses now provide useful server
details. The default model is `qwen2.5:7b-instruct`.

### Static guard

`versionguard/check.py` parses Python with the AST, resolves imported library
names and checks selected attribute chains and trustworthy keyword signatures
against the current installed versions. Findings include syntax errors,
missing APIs, wrong keywords, unavailable modules and deprecation warnings.
Outputs support readable diagnostics, JSON and GitHub annotations.

Regression fixes constrain protective `hasattr`/`getattr` exemptions to matching
owners and protective branches. OR conditions and truthy defaults cannot hide
invalid calls. GitHub annotation properties and messages are escaped. Invalid
or empty targets produce a command error rather than an apparent successful
scan.

Bot answers include static findings when the requested library version matches
the local installation. A mismatch is reported as `not_checked`; a clean scan
does not mean functional tests passed. This is a name-based checker, not full
type inference, and cannot generally resolve methods on runtime values such
as `df.append(...)`.

### Repair behavior

The bot accepts paired `--code` and `--error-log` inputs, retrieves documentation
and proposes a replacement. It reads but does not overwrite or execute the
original program. Plain guard/build diagnostics are preserved. Tracebacks and
assertion feedback are sanitized before being shown to the model.

In the benchmark, each repair condition retries failures from the version-only
condition once. Already-passing attempts retain their pass without another
generation. The benchmark prompt definitions and scoring contract were kept
unchanged during the later standalone repair and integration work.

### Evaluation and integrity controls

`experiment/prepare.py` builds environments, checks reference solutions,
extracts documentation and caches retrieval. Cache replacement is atomic;
failed reference records are persisted. Verification refuses incomplete or
empty preparation.

`experiment/executor.py` uses Linux/AMD64 Docker images per pinned environment.
Generated benchmark programs run with network disabled, memory/CPU/PID limits,
a read-only filesystem, a temporary filesystem and execution time limits.
The host executor is used for trusted fixture self-checks, not real benchmark
answers.

`experiment/run.py` requires Docker and usable preparation for real runs,
checks task/cache environment identity and dataset/split hashes, and writes
each completed cell immediately. Resume rejects incompatible settings,
model digests, Ollama versions, timeout and recorded input identities.
Interruptions preserve completed results.

`experiment/report.py` detects duplicate cells and incompatible metadata,
reports coverage, excludes legitimate unavailable oracle cells from their
denominator and supports `--model` and `--require-complete`. It exports
summary, comparison and failure CSVs. Cross-model reporting checks input
hashes, generation settings and Ollama versions. Timing excludes carried
passes and skipped cells.

## 4. Completed evaluation

The dataset is GitChameleon 2.0. The fixed selection contains 60 tasks:
NumPy 6, SciPy 27 and SymPy 27, spanning 15 pinned environments. Development
has 20 tasks; held-out test has 40. Nine NumPy 1.21.0 tasks were excluded before
evaluation because of prebuilt-package compatibility, as documented in the
split and protocol. This selection limits generalization beyond these tasks.

| Setting | Value |
|---|---|
| Model | `qwen2.5:7b-instruct` |
| Model digest prefix | `845dbda0ea48` |
| Runtime | Ollama 0.35.0, Windows AMD64, host Python 3.12.3 |
| Executor | Docker, pinned task-specific Python/library versions |
| Temperature / seed | 0.0 / 42 |
| Context / generated output cap | 4096 / 768 tokens |
| Retrieved entries / documentation budget | 3 / 2400 characters |
| Execution timeout | 120 seconds per test run |

| Split | Tasks | Condition records | Actual generations | Carried cells | Oracle skips | Elapsed |
|---|---:|---:|---:|---:|---:|---|
| Development | 20 | 120 | 90 | 20 | 10 | 12.2 minutes |
| Held-out test | 40 | 240 | 186 | 36 | 18 | 26.2 minutes |

All expected cells were verified exactly once. Recorded program failures are
model-answer outcomes, not missing environment preparation. No environment
errors were found in the held-out audit. Neither 360 condition records nor 240
test records should be described as that many independent model calls.

### Held-out results

| Condition | Passed | Rate |
|---|---:|---:|
| Task only | 21/40 | 52.5% |
| Version only | 18/40 | 45.0% |
| Version plus retrieved docs | 21/40 | 52.5% |
| Oracle/reference API docs | 10/22 | 45.5% |
| One repair round, log only | 22/40 | 55.0% |
| One repair round, log plus docs | 22/40 | 55.0% |

| Primary comparison | Difference | 95% paired-bootstrap interval | Permutation p | Registered decision |
|---|---:|---|---:|---|
| Lookup vs version only | +7.5 points | [-7.5, +22.5] | 0.510 | No effect detected |
| Repair docs vs repair log | 0.0 points | [-7.5, +7.5] | 1.000 | No effect detected |

The registered rule requires at least +10 points and a 95% interval entirely
above zero, separately for each model. Neither primary Qwen comparison meets
it. Failure to meet the rule is not proof that documentation never helps.

Each repair method fixes 4 of the 22 failed version-only attempts, but they fix
different tasks. The descriptive repair-vs-no-repair gain is +10 points; it
does not demonstrate an additional documentation benefit. Its permutation
p-value is 0.126, so the final narrative should distinguish the registered
bootstrap rule from conventional p-value significance.

Lookup matched a reference API on 19 of the 22 oracle-eligible tasks. This is
a useful diagnostic, but the three misses are too few to support a causal
retrieval conclusion. API-missing failures decrease from 6 with version only
to 2 with lookup, while wrong-result failures increase from 10 to 13. Matching
API documentation is therefore insufficient to ensure correct task behavior.

Development results are pipeline evidence, not the primary scientific result.
Lookup passes 7/20 dev tasks versus 10/20 with version only, reinforcing that
documentation is not uniformly helpful across this small selection.

## 5. Verification and fixes

Latest full local verification: **89 tests passed and 2 subtests passed** in
the project virtual environment, plus Ruff. Core coverage is 69% rounded
(68.91%); configured coverage includes `versionguard/` and `experiment/`, not
helper scripts. Guard coverage is 85%, report 94% and code parsing 95%.
Fetch/selection and some documentation/executor paths have lower automated
coverage; real preparation and Docker runs provide additional operational
evidence, not replacement unit coverage.

The GitHub workflow YAML parsed successfully, and its lint, test, fixture and
guard steps were exercised locally. The scripted fixture run produced all 36
expected cells. That synthetic result verifies the pipeline and is not model
performance evidence.

The local guard demo under NumPy 1.26.4 rejects `np.asscalar` with `VG001` and
accepts the corrected example. An independent Qwen repair initially proposed
invalid `np.item(array)`. That failed proposal was saved. With revised standalone
retrieval and a clarified question, Qwen proposed `array.item()`, which passed
NumPy 1.25.0 Docker checks for integer, float, scalar, one-element
multidimensional input and rejection of multiple elements. This revised-input
example is illustrative; it is not an unbiased repair success-rate measurement.

Material issues addressed during development include incomplete preparation
being treated as runnable, mixed resume configurations, unhelpful HTTP 500
diagnostics, missing source targets, unsafe annotation formatting, overbroad
guard exemptions and noisy standalone repair search terms. A locally observed
model failure motivated proposal validation rather than a claim that all
generated code is correct.

The earlier coverage baseline is preserved. No Qodo improvement is claimed:
current tests are project-authored, and generated-test provenance must be
recorded separately when Qodo is used.

## 6. Integration and delivery

The CI workflow has read-only repository permissions, Python 3.12, pinned NumPy
for the demo, coverage artifacts and changed-file guard checks. Changed-file
selection preserves spaces and covers application directories; expected-invalid
tests/fixtures are excluded from that scan and covered by tests. Hosted
execution and branch protection are not yet verified.

The local PR repair helper uses GitHub CLI to fetch a regular Python file at a
fixed PR head, invokes the existing bot and writes Markdown/JSON previews.
Explicit `--post` rechecks the head and creates or updates the authenticated
user's marked VersionGuard comment. PR code is not checked out or executed.
Tests cover stale-head rejection, preview persistence, owned-comment updates,
path traversal and model Markdown containment. Network/API behavior is mocked;
no actual posting is yet evidenced. This is a maintainer-operated local path,
not automatic hosted repair or an automatic patch/merge service.

The teammate ZIP contains 83 checksum-verified files. A fresh-directory
extraction reproduced the Qwen test report exactly. It includes source,
workflows, fixed dataset/split/cache, results and instructions; excludes model
weights, environments, credentials and scratch data. The latest assignment is
`codellama:7b-instruct`, replacing the earlier Llama 3B plan.

CodeLlama is a different code-focused model at roughly the same parameter
scale as Qwen. This supports a comparison across model families; better results
are not guaranteed. Matching parameter count does not control training data,
architecture, quantization or inference behavior. Model digests must be retained.
Mac inference timing must be reported separately from Windows timing.

The user has reported sending the teammate work. No second-model files or
external verification evidence have been returned yet. The original local
checkout still has untracked source and no configured Git remote; a committed,
hosted source baseline remains a delivery prerequisite.

## 7. Remaining work and acceptance criteria

| Priority | Work | Responsible party | Completion evidence |
|---|---|---|---|
| P0 | Establish a hosted, committed source baseline | Project owner with teammate | Repo URL, source commit, frozen split/cache included |
| P0 | Verify pinned environments on Mac | Teammate | All selected references pass; mismatches resolved before model evaluation |
| P0 | CodeLlama dev smoke and full test evaluation | Teammate | Standard JSONL + metadata, 40 tasks, 240 unique test cells, no environment errors |
| P0 | Validate returned results and merge report | Core owner | Import validation succeeds; complete two-model report generated |
| P1 | Run hosted CI and protect main | Teammate/project owner | Green Actions run and configured required check |
| P1 | Demonstrate guard failure and corrected pass | Teammate | Real PR URL, line annotation, red/green screenshots |
| P1 | Exercise live repair preview/post flow | Teammate | Saved preview and posted commit-specific comment; no claim of unrun tests |
| P1 | Inspect failures across models | Both | Task IDs, proposed code, actual errors and explained categories |
| P1 | Final technical/progress report and slides | Both | Two-model tables, uncertainty, limitations and demo evidence |
| P2 | Qodo tests and coverage comparison | Teammate | Generated-test provenance, kept/discarded counts, comparable before/after run |
| P2 | Sweep integration | Teammate | Actual Sweep PR and CI evidence, or recorded installation limitation |

Current scope does not require another Qwen test run. Returned CodeLlama data
must match the registered settings and fixed input hashes. The existing
validator checks these and refuses conflicting result overwrites. Hosted
credentials and repository access are needed for external integration; no
extra application implementation is required to start those validations.

## 8. Residual limits and follow-on engineering

1. **Scientific scope:** 40 held-out tasks and one completed model give wide
   intervals. Oracle coverage is partial. Library distribution is uneven and
   the selection excludes an incompatible pinned version. Training-data overlap
   is not controlled. General production benefit is unproven.
2. **Guard completeness:** runtime-value methods and some dynamic imports or
   call signatures cannot be resolved. Conditional findings can be warnings.
   Missing optional packages warn in the minimal CI environment. The guard
   imports installed libraries to inspect them; it is not a general untrusted
   package sandbox.
3. **Version scope:** current CI dependencies support the NumPy demonstration
   and this project's checks. Applying the workflow to another repository
   requires that repository's pinned libraries; it does not automatically
   discover and reproduce every possible application environment.
4. **Reproducibility:** completed test metadata includes input hashes; older dev
   metadata lacks dataset/split hash fields. Legacy compatibility preserves that
   limitation rather than fabricating provenance. Requirements use ranges and
   Docker base tags are not immutable image digests, so stronger dependency and
   image locking is a future hardening task.
5. **Integration evidence:** Windows checks do not prove Linux hosted behavior
   or Mac Docker compatibility. Mocked PR tests do not establish authenticated
   API behavior. Live checks are the next acceptance gate.
6. **Product scope:** the tool is a CLI prototype. It has no web application,
   automatic repair execution, automatic commits/merges or deployed service.
   Static cleanliness and a proposed repair must not be presented as a tested
   correction. Docker limits reduce execution exposure but are not proof of
   isolation against every hostile program.
7. **Future improvement:** inspect retrieved evidence and wrong-result failures
   before changing lookup or prompts. Any tuning after viewing test outcomes
   requires a separately identified experiment and a fresh evaluation design;
   preserve the current benchmark results.

## 9. Evidence index

Paths are relative to the project root.

| Evidence | Location |
|---|---|
| Registered study contract | `experiment/PROTOCOL.md` |
| Fixed selection and lookup | `experiment/splits/split.json`, `experiment/retrieval_cache.json` |
| Qwen raw dev data and metadata | `results/dev-qwen2.5_7b-instruct.jsonl`, matching `.meta.json` |
| Qwen raw held-out data and metadata | `results/test-qwen2.5_7b-instruct.jsonl`, matching `.meta.json` |
| Reports and exports | `results/report-dev.md`, `results/report-test.md`, summary/comparison/failure CSVs |
| Repair and guard demonstrations | `results/repair-demo*.json`, `results/guard-demo.json` |
| Integration verification | `results/integration-validation.md` |
| Coverage before/after integration | `results/coverage-baseline.json`, `results/coverage-integration.json` |
| CI | `.github/workflows/ci.yml`, `requirements-ci.txt` |
| Teammate assignment | `docs/HANDOFF.md`, `docs/TEAMMATE.md` |
| Delivery | `deliverables/VersionGuard-teammate.zip`; manifest inside ZIP |

This report was prepared from current source, saved verification evidence,
result metadata and a read-only audit of task/cell counts. No evaluations or
full test suites were rerun while preparing it. The report is a new local
artifact and is not included in the already-sent delivery archive.
