# Mid-Term Completion Workflow

Date: 8 October 2026. Assessment window: 5-9 October 2026.

The project owner completes core development, integration and submissions.
The teammate's remaining assignment is only CodeLlama 7B evaluation on the Mac
and returning its results, metadata and environment-verification log.

## Work sequence

| Stage | Action | Acceptance evidence | Current status |
|---|---|---|---|
| 1 | Revise ownership and handoff | `docs/EVALUATION_ONLY.md` | Complete |
| 2 | Create one local verification entry point | `scripts.verify`; saved successful checks, 92 tests + 2 subtests | Complete |
| 3 | Demonstrate the real RAG bot and repair | Saved real answer and independent Docker outcomes; retrieval weaknesses disclosed | Complete within documented limits |
| 4 | Provide generated-test workflow | Actual Qodo service notice; Codeium/Windsurf installed, isolated prompt and fresh 92-test baseline | Editor login/generation and review pending |
| 5 | Finish assessment documents | Charter, timeline, report, demo guide, contribution log and live evidence | Complete; final rehearsal is personal work |
| 6 | Host source and run Actions | Published main and actual green Actions run | Complete |
| 7 | Demonstrate a failing and fixed PR | PR #1; actual VG001 annotation and red/green run links | Complete |
| 8 | Run live PR repair and Sweep | Commit-specific repair comment posted; legacy Sweep access limitation recorded | Repair complete; Sweep rubric evidence pending |
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

See `docs/LIVE_EVIDENCE.md` for verified hosted links and external-tool findings.
Named-tool requirements need supported access or an instructor-approved
alternative. Tool-authored evidence must come from the actual named tool.
