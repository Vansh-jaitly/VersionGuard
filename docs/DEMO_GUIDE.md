# Working Prototype Demonstration

Use a prepared environment with Qwen, Docker and cached documentation. This is a
demonstration, not another held-out benchmark run. Preserve failed proposals.

## 1. RAG answer and sources

```powershell
python -m experiment.doctor --model qwen2.5:7b-instruct
python -m scripts.rag_demo --retriever vector
```

Inspect `results/rag-demo.json`: question, retrieved source names, answer,
static guard status and pinned Docker test outcome. Explain that LangChain/Chroma
handles retrieval even if Ollama generation uses its HTTP fallback. A static
version mismatch is `not_checked`, not a fabricated clean check. The saved
vector demonstration retrieved unrelated sources despite a passing answer;
explain that retrieval quality remains a limitation.

## 2. Removed API and correction

```powershell
python -m scripts.guard_demo
```

Show `results/guard-demo.json`: `np.asscalar` fails with VG001, corrected code
passes. The invalid example is stored as text so it does not break ordinary lint.
The real GitHub demonstration places it in a changed `.py` file, observes a red
guard check, then replaces it with the fixed example and observes green.

## 3. Repair and test

Use `versionguard.ask` with paired `--code` and `--error-log` on a local example.
Explain that it proposes a replacement without modifying or executing the
original. Show separately recorded Docker verification. The initial invalid
`np.item` proposal and corrected `array.item()` evidence remain available.

## 4. Integration checks

```powershell
.venv\Scripts\python.exe -m scripts.verify
```

Show logs and `results/verification/summary.json`. It records lint, full tests,
coverage, fixture run/report, guard demo and unchanged fixed benchmark hashes.
Fixtures use scripted models; their high pass rate is not Qwen performance.

## 5. Actual GitHub evidence

Open the actual links in `docs/LIVE_EVIDENCE.md`: green baseline, PR #1, red
guard run, Qwen comment and corrected green run. PR repair uses local Ollama and explicit posting;
it does not deploy or automatically merge code. Sweep and named AI-test generation
must have their own real provenance. Current named-tool availability limitations
are recorded; those rubric items are not claimed complete. Show
`results/live-pr-verification.json`: the model's static-clean proposal failed,
while the reviewed correction passed independently in Docker.

## 6. Evaluation conclusion

Present the 40-task Qwen report: version 45%, lookup 52.5%, both repairs 55%.
Neither primary documentation comparison meets the fixed success criterion.
Explain confidence intervals and why a working prototype can coexist with an
inconclusive research finding. CodeLlama results are pending from the teammate.
