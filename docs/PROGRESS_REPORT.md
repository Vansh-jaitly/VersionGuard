# VersionGuard: Mid-Term Progress Report

**Date:** 8 October 2026  
**Assessment:** Integration of AI tools, code retrieval and automation workflows  
**Repository:** https://github.com/Vansh-jaitly/VersionGuard

## Objective and prototype

VersionGuard addresses Python code generated for the wrong library version.
It retrieves documentation from a pinned installation, proposes code through
local Ollama, statically checks selected API calls, and proposes a repair from
failed code plus its error log. The application has three core commands:
`versionguard.ask`, `versionguard.check` and `experiment.run`.

The stack is Python, LangChain/Chroma, local all-MiniLM-L6-v2 embeddings,
Ollama and Docker. BM25 offers keyword retrieval. The Ollama client has a direct
HTTP fallback. Documentation is extracted from installed libraries rather than
assuming the newest online documentation matches an older version.

## Implemented and verified work

The core bot, retrieval, static guard, source/log repair, Docker executor,
resumable six-condition runner and report generator are implemented. Preparation
checks benchmark reference solutions before scoring model answers. Input hashes,
pinned environment details and generation settings are recorded; conflicting
resumes and incomplete results are rejected or flagged. API findings support
readable output, JSON and GitHub line annotations.

CI configuration runs lint, tests/coverage, the fixture pipeline and a removed-API
guard demo. Local PR tooling reads source at a fixed commit, saves a repair preview
and explicitly posts only after checking that the PR has not changed. Hosted
baseline CI is green. PR #1 records the removed-API guard failure, Qwen repair
comment and corrected green run. Independent Docker checks confirm that the
model's static-clean `np.isscalar` proposal is wrong and the reviewed
`array.item()` correction passes. See `docs/LIVE_EVIDENCE.md` for links.

Latest saved completion verification: 92 tests and 2 subtests passed, Ruff
passed, and core statement coverage was 69%. A 36-cell synthetic fixture pipeline
passed its expected-outcome checks. The guard rejected removed `numpy.asscalar`
and accepted the correction. Independent NumPy 1.25.0 Docker checks verified a
Qwen proposal using `array.item()`; the initial invalid proposal was preserved.
These demonstrations are not substituted for benchmark performance.

## Evaluation and findings

The fixed GitChameleon study contains 20 dev and 40 held-out tasks across NumPy,
SciPy and SymPy in 15 environments. Qwen 2.5 7B Instruct completed the dev run
in 12.2 minutes and test run in 26.2 minutes. All 360 condition records are present:
276 actual generations, 56 carried initial passes and 28 unavailable oracle cells.

| Held-out condition | Passed |
|---|---:|
| Task only | 21/40 (52.5%) |
| Version only | 18/40 (45.0%) |
| Retrieved documentation | 21/40 (52.5%) |
| Reference-API documentation | 10/22 (45.5%) |
| One repair round, log only | 22/40 (55.0%) |
| One repair round, log plus docs | 22/40 (55.0%) |

Lookup gains 7.5 points over version only, with a 95% interval [-7.5, +22.5].
Documentation adds 0 points to repair, with interval [-7.5, +7.5]. Neither meets
the predeclared +10-point gain and positive-interval rule. The outcome is
inconclusive for documentation benefit, not evidence that the implemented
retrieval or guard is nonfunctional. Wrong-result failures remain the dominant
lookup failure category, illustrating the gap between finding an API and using
it correctly.

## Progress, contribution and next steps

Core development and first-model evaluation are complete. The owner now retains
CI, named-tool integration, testing evidence and documents. The teammate is
assigned only reference verification and CodeLlama 7B evaluation on the Mac;
returned JSONL/metadata will be validated before creating the combined report.

Hosted Actions, the guard-failing then corrected PR and live repair comment are
complete. Authenticated Qodo Command returned a service-discontinued notice and
generated no tests. Sweep's official README now points to JetBrains; two legacy
GitHub app names returned 404. Named-tool test-generation and Sweep rubric evidence
therefore remain unmet pending supported access or an instructor-approved
alternative. Existing tests are not tool-generated. Contribution records disclose
AI assistance and distinguish work assignment from completion.

Known limits include partial oracle availability, a small selected benchmark,
name-based rather than full type-aware static checking, dependency ranges and
limited automated coverage of external APIs. No frontend, production deployment or
automatic merge service is claimed. The charter, timeline, technical report,
walkthrough and saved verification artifacts support the working demonstration.
