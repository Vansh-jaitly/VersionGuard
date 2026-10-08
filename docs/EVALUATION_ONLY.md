# Teammate Assignment: CodeLlama Evaluation Only

**Delivery update, 8 October 2026:** The five-task dev smoke, complete held-out
run and 60/60 reference log have been received. Standalone validation passes;
combined comparison has an Ollama 0.32.15 versus 0.35.0 limitation. See
[TEAMMATE_INTAKE.md](TEAMMATE_INTAKE.md). The instructions below are the original
assignment, not a request to rerun the completed evaluation.

This supersedes earlier instructions assigning CI, Sweep, AI tests or documents
to the teammate. The project owner is completing those deliverables.

Use the supplied fixed dataset/split/cache, Python 3.12, Docker Desktop and
Ollama 0.35.0. Do not rebuild retrieval, reselect tasks, change settings or rerun
Qwen. Install model only if absent:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt -r requirements-dev.txt
ollama list
ollama pull codellama:7b-instruct
python -m experiment.doctor --model codellama:7b-instruct
python -m experiment.prepare --split all --verify-only --executor docker
python -m experiment.run --split dev --model codellama:7b-instruct --executor docker --limit 5
python -m experiment.run --split test --model codellama:7b-instruct --executor docker
python -m experiment.report --split test --model codellama:7b-instruct --require-complete
```

Stop and report any failed reference/environment check. Interrupted evaluation
resumes with the same command; do not use `--force`. Container environments are
Linux/AMD64 even on Apple Silicon, so startup/build speed can differ.

Return together:

- `results/test-codellama_7b-instruct.jsonl`
- `results/test-codellama_7b-instruct.meta.json`
- Reference/environment verification log and your run notes.

Report model performance honestly, including failures. No result threshold is
required for a valid completed evaluation. The core owner validates/imports the
files and produces the combined report. Do not return modified Qwen data.
