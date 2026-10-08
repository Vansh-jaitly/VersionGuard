# Revised Timeline: Progress vs Plan

Status date: 8 October 2026. Mid-term window: 5-9 October 2026.
Dates below distinguish recorded completion from targets, not invented history.

| Phase from original plan | Current progress | Evidence | Next action / target |
|---|---|---|---|
| 1. Skeleton and command contract | Complete | Three core CLI commands and fixture tasks | Preserve interface |
| 2. Loader, environments and baseline conditions | Complete | Fixed dataset/split; 60 reference checks; Docker runs | Teammate verifies Mac environments |
| 3. Lookup and oracle conditions | Complete | LangChain/Chroma retrieval and frozen per-task cache | Demonstrate live RAG bot |
| 4. Repair and guard | Complete locally | Static guard, repair proposal, Docker demo, regression tests | Exercise on hosted PR |
| 5. Full models and reporting | Qwen complete on 8 Oct; CodeLlama pending | 120 dev and 240 test cells; reports/metadata | Teammate returns CodeLlama files |
| 6. Workflow and automation | CI and PR helpers implemented | Workflow, local checks, mocked API tests | Hosted run, failing/fixed PR and Sweep evidence |
| 7. AI-generated tests | Access/provenance work pending | Existing authored tests and coverage baseline | Actual accepted-tool output and equivalent coverage comparison |
| 8. Documents and demo rehearsal | Implementation in current phase | Charter, timeline, progress report, demo guide | Final evidence review and rehearsal by 9 Oct, subject to access |

## Current work order

1. Finish repeatable verification and live Qwen RAG demonstration on 8 Oct.
2. Establish the source baseline and run hosted CI once GitHub authentication is available.
3. Capture red/green PR checks and review/post a repair proposal.
4. Complete named-tool test-generation and Sweep evidence, or document concrete blockers.
5. Assemble the mid-term submission and explain findings/limitations.
6. Independently receive, validate and report CodeLlama results when returned.

## Ownership revision

Project owner: implementation, CI, automation, test-generation evidence, documentation,
integration validation and final reporting. Teammate: CodeLlama 7B environment
verification and model evaluation only. Each student should record concrete work
and understanding; assigned work is not evidence of completion.

## Dependencies and progress reporting

Hosted CI/PR automation depends on authenticated repository access. Named-tool
evidence depends on the actual tool/account being available. Qwen data and core
prototype do not depend on the teammate's speed. Target dates are not guarantees:
leave unresolved steps marked pending rather than presenting them as completed.
