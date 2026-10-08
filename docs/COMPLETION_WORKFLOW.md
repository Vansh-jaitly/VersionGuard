# Mid-Term Completion Workflow

Date: 8 October 2026. Assessment window: 5-9 October 2026.

The project owner completes core development, integration and submissions.
The teammate's remaining assignment is only CodeLlama 7B evaluation on the Mac
and returning its results, metadata and environment-verification log.

## Work sequence

| Stage | Action | Acceptance evidence | Initial status |
|---|---|---|---|
| 1 | Revise ownership and handoff | Teammate instructions only require the second evaluation | In progress |
| 2 | Create one local verification entry point | Lint, full tests, fixture report and guard demo run; artifacts saved | Planned |
| 3 | Demonstrate the real RAG bot and repair | Qwen answer, retrieved sources, guard findings and pinned Docker outcome | Planned |
| 4 | Provide generated-test workflow | Accepted tool provenance, reviewed tests and comparable coverage reports | Access investigation |
| 5 | Finish assessment documents | Charter, progress timeline, concise report, demo guide and contribution log | Planned |
| 6 | Host source and run Actions | Source commit, repository URL and actual green Actions run | Repository details required |
| 7 | Demonstrate a failing and fixed PR | Actual annotations and red/green CI run links | Depends on stage 6 |
| 8 | Run live PR repair and Sweep | Actual posted repair, Sweep PR or documented availability limitation | Depends on tool access and stage 6 |
| 9 | Import CodeLlama results when returned | Validation succeeds and complete combined report generated | Teammate evaluation pending |

## Scope and fixed research inputs

Do not rerun completed Qwen benchmark cells, modify the split/cache/protocol or
replace inconclusive findings with selected favorable examples. New demonstrations
are separately labeled. Neither a working guard nor a passing demo proves the
registered documentation-benefit hypothesis.

CI and evaluation are different: CI verifies our implementation with fixtures;
real model evaluation scores generated programs in task-specific Docker images.
PR repair is a local maintainer command, not automatic deployment or merging.

## Assessment evidence

- RAG bot: actual question, pinned version, retrieved source names and answer.
- LangChain: actual Chroma/embedding retrieval path, distinct from Ollama's HTTP fallback.
- GitHub Actions: live run link; local verification cannot substitute for it.
- Sweep: tool-generated change/PR and CI link, or an explicit recorded limitation.
- CodiumAI/Qodo or accepted Codeium tool: exact tool/version, generated tests,
  retained/discarded counts and equivalent baseline/after coverage measurements.
- Integration/documentation: reproducible commands, working prototype and clear limits.
- Individual contribution: concrete reviewed/tested work with attributable history;
  AI assistance is disclosed rather than attributed as unaided student authorship.

External actions await the required repository/account access. Tool-authored
evidence must come from the actual named tool, not manually fabricated labels.
