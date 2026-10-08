# VersionGuard: Technical Status Report

**Audience:** Senior engineering review  
**Date:** 8 October 2026, Asia/Calcutta  
**Scope:** Current implementation, both model evaluations, hosted integration
verification, teammate handoff and remaining delivery work.

## 1. Engineering assessment

VersionGuard is a working CLI research prototype with two independent held-out
model runs and verified integration tooling. The core build phase is
complete. Hosted CI and the PR demonstration are verified, and both model
datasets are audited. The combined inference-runtime mismatch and named-tool rubric evidence
remain outstanding.

The application can retrieve documentation for a pinned library version,
propose code or repairs using local Ollama, flag selected invalid library calls,
execute benchmark answers in pinned Docker environments, and produce paired
statistical reports. GitHub CI and a local PR repair-comment path are written
and verified on GitHub. `docs/LIVE_EVIDENCE.md` contains actual run/comment links
and independent verification outcomes. A delivery ZIP has been produced, and the user
reports having sent the teammate work. Its returned folder is now inspected;
the raw CodeLlama data and reference log are preserved. Local replay validates
the nine repair gains, rather than independently witnessing the Mac generation process.

The primary research claim is not established by the completed Qwen run.
Documentation lookup improves the observed pass rate by 7.5 percentage points,
but the confidence interval crosses zero and the gain is below the registered
10-point threshold. Documentation adds no aggregate gain to the repair round.
These findings must remain part of the final report even if the second model
performs better.

The returned CodeLlama run now supplies a positive model-specific repair result:
42.5% log-only versus 65.0% log-plus-docs, +22.5 points with a 95% interval
[+10.0, +35.0] and p=0.005. Its standalone report passes strict validation and
all nine paired repair gains replayed in local pinned Docker. The combined
comparison remains provisional because the Mac used Ollama 0.32.15 while Qwen
used 0.35.0. See `docs/TEAMMATE_INTAKE.md`; do not infer a controlled ranking
of the two models from this mixed-runtime comparison.

## 2. Delivery status

| Component | Implementation | Evidence and remaining boundary |
|---|---|---|
| Bot and pinned-version documentation lookup | Complete | Real Ollama and cached vector retrieval used |
| Static library API guard | Complete within stated limits | Tests and local NumPy failure/pass demo |
| Benchmark preparation and Docker executor | Complete | All 60 selected tasks prepared across 15 environments |
| Six-condition evaluation runner | Complete | Qwen full dev/test, CodeLlama five-task smoke and full held-out test |
| Standalone repair command | Complete | Independent repaired NumPy example tested in Docker |
| Reporting and result import | Verified | Qwen and standalone CodeLlama reports reproduced; mixed-runtime comparison remains provisional |
| GitHub Actions workflow | Verified hosted | Green baseline and red/green guard PR; see live evidence |
| PR repair preview/posting helper | Verified live | Commit-specific Qwen comment posted; wrong proposal preserved and independently tested |
| Teammate delivery archive | Revised | Evaluation-only scope; earlier 83-file archive sent according to user |
| CodeLlama 7B evaluation on teammate Mac | Returned and audited | 40 tasks/240 cells, five-task dev smoke, 60/60 reference log; 9/9 repair gains replayed |
| Qodo and Sweep evidence | Attempted; external limitations | Qodo CLI discontinued notice; two legacy Sweep app names returned 404; rubric items unmet |
| Submission documents | Complete for current evidence | Charter, timeline, brief progress report, demo guide and contribution disclosure |
| Combined report and presentation | Provisional report ready | Ollama mismatch disclosed; student rehearsal/presentation pending |

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

Latest full local verification: **92 tests passed and 2 subtests passed** in
the project virtual environment, plus Ruff. Core coverage is 69% rounded
(68.91%); configured coverage includes `versionguard/` and `experiment/`, not
helper scripts. Guard coverage is 85%, report 94% and code parsing 95%.
Fetch/selection and some documentation/executor paths have lower automated
coverage; real preparation and Docker runs provide additional operational
evidence, not replacement unit coverage.

The GitHub workflow passed on a fresh Ubuntu checkout, including lint, tests,
coverage, fixture report and guard demonstration. Its first run exposed an
import test that required locally downloaded benchmark data; a temporary
synthetic input now makes the test independent. The fixture run produced all 36
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
execution is verified with actual red/green run links. Main is not branch-protected.

The local PR repair helper uses GitHub CLI to fetch a regular Python file at a
fixed PR head, invokes the existing bot and writes Markdown/JSON previews.
Explicit `--post` rechecks the head and creates or updates the authenticated
user's marked VersionGuard comment. PR code is not checked out or executed.
Tests cover stale-head rejection, preview persistence, owned-comment updates,
path traversal and model Markdown containment. Live posting is evidenced by
PR #1's commit-specific comment. Qwen proposed `np.isscalar(array)`, which the
guard accepted but Docker tests rejected for wrong output. The reviewed
`array.item()` correction passed Python 3.12 / NumPy 1.26.4 Docker checks and
hosted CI. This is a maintainer-operated local path,
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

The user has reported sending earlier teammate work. The revised scope is only
CodeLlama environment verification and evaluation (`docs/EVALUATION_ONLY.md`).
CodeLlama files are returned and accepted independently; side-by-side results
are saved with an Ollama-version warning. The source is committed and
published at https://github.com/Vansh-jaitly/VersionGuard. All hosted links are
indexed in `docs/LIVE_EVIDENCE.md`. Qodo Command 0.36.0 was installed,
authenticated and attempted with an approved isolated input, but the actual
service returned a discontinued notice and generated no tests. Sweep's official
README points to JetBrains; checked GitHub app names `sweep` and `sweep-ai`
returned 404. These named-tool requirements remain unmet.

## 7. Remaining work and acceptance criteria

| Priority | Work | Responsible party | Completion evidence |
|---|---|---|---|
| P0 | Resolve or explicitly retain inference-runtime limitation | Project owner | Ollama mismatch remains visible; any requested replication preserves original data |
| P1 | Inspect failures across models | Both | Task IDs, proposed code, actual errors and explained categories |
| P1 | Student presentation and final evidence review | Project owner | Standalone model findings, provisional comparison, uncertainty and actual demo evidence |
| P2 | Named-tool tests and coverage comparison | Project owner | Supported tool or instructor-approved alternative, actual generation and comparable coverage |
| P2 | Sweep rubric evidence | Project owner | Supported integration or instructor acceptance of documented availability limitation |

Current scope does not require another Qwen test run. Returned CodeLlama data
must match the registered settings and fixed input hashes. The existing
validator checks these and refuses conflicting result overwrites. Hosted
access is established. Remaining named-tool work depends on supported services
or an instructor-approved alternative. Optional main branch protection remains
a hardening choice, not a completed control.

## 8. Residual limits and follow-on engineering

1. **Scientific scope:** 40 held-out tasks and two local models give wide
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
5. **Integration evidence:** Linux hosted checks and actual PR posting are now
   verified. They do not establish Mac Docker compatibility or comprehensive
   handling of every external API failure. Qodo/Sweep rubric evidence is incomplete.
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
| Hosted Actions/PR evidence and tool limitations | `docs/LIVE_EVIDENCE.md`, `results/live-pr-*.json`, `results/tool-availability/` |
| CodeLlama intake and independent gain replay | `docs/TEAMMATE_INTAKE.md`, `results/incoming/codellama-mac/` |
| Provisional two-model report | `results/model-comparison/report-test.md`, matching CSVs |
| Coverage before/after integration | `results/coverage-baseline.json`, `results/coverage-integration.json` |
| CI | `.github/workflows/ci.yml`, `requirements-ci.txt` |
| Teammate assignment | `docs/HANDOFF.md`, `docs/TEAMMATE.md` |
| Delivery | `deliverables/VersionGuard-teammate.zip`; manifest inside ZIP |

This report was updated from source, saved verification, actual hosted runs,
PR comments and tool-service responses. Frozen Qwen benchmark cells were not
rerun. The current regenerated delivery includes this report; the user's earlier
sent archive is a historical package, not proof of delivery of this revision.
