# Updated Project Charter / Synopsis

**Project:** VersionGuard  
**Revision:** 8 October 2026, mid-term assessment  
**Repository:** https://github.com/Vansh-jaitly/VersionGuard

## Problem and objective

AI-generated Python can use APIs or arguments absent from the project's installed
library version. VersionGuard retrieves documentation from the pinned version,
checks selected API calls and proposes repairs after build/test failures.
The objective is a working, reproducible tool and an honest evaluation of whether
documentation improves local-model code generation and repair.

## Scope

- RAG Q&A bot using LangChain/Chroma and local embeddings, with local Ollama generation.
- Static installed-version API guard with CLI, JSON and GitHub annotations.
- Standalone source/log repair proposals and reviewable PR-comment integration.
- Docker evaluation on fixed GitChameleon tasks with six evidence conditions.
- GitHub CI, AI-test generation evidence and Sweep automation where access is available.
- Working documentation, contribution records and mid-term demonstration.

The prototype does not train a model, automatically deploy a service, merge PRs
or guarantee semantic correctness from a static scan. Real answer scoring comes
from pinned Docker tests.

## Method and acceptance

The fixed study contains 20 development and 40 held-out tasks, covering NumPy,
SciPy and SymPy. Compare task-only, version-only, retrieved docs, reference-API
docs, log repair and log-plus-doc repair. Qwen 7B is complete; CodeLlama 7B is
the second approximately same-size model, assigned to the teammate's Mac.
Primary documentation benefit needs a gain of at least 10 percentage points and
a 95% paired-bootstrap interval wholly above zero, separately for each model.

The engineering prototype must demonstrate retrieval, model response, guard
failure/correction, independently tested repair and repeatable verification.
Named-tool rubric evidence must identify the actual tool used; local/mock evidence
must not be presented as live GitHub or Sweep execution.

## Current progress and scope revision

Core generation, retrieval, guard, repair, evaluation and reporting are implemented.
Qwen's completed evaluation does not meet either primary benefit criterion:
lookup improves from 45.0% to 52.5% but its interval crosses zero, and both repair
paths pass 55.0%. This outcome is preserved.

The project owner now owns all integration and assessment deliverables. The
teammate owns only environment verification and the CodeLlama evaluation,
returning JSONL and metadata. This supersedes the earlier division assigning
CI, tools and documents to the teammate.

## Risks and mitigations

- Small task set: report uncertainty and avoid broad performance claims.
- Model hallucination: show static findings and execute proposals in pinned Docker.
- Cross-machine differences: verify references, freeze retrieval and record hashes/settings.
- Tool/account access: distinguish implemented workflows from live external evidence.
- Assessment timing: prioritize required integration evidence and concise submissions;
  the second-model comparison can arrive independently.

## Submission artifacts

Updated charter, progress timeline, working source/demo, 1-2-page progress report,
verification logs, generated-test provenance and individual contribution record.
