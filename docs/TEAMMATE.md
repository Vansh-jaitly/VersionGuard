# Second person's task list

**Scope update, 8 October 2026:** Your only remaining responsibility is the
CodeLlama 7B evaluation. Follow [EVALUATION_ONLY.md](EVALUATION_ONLY.md).
The project owner completes CI, Sweep, generated-test evidence and documents.
All broader responsibilities in the original checklist below are superseded.

Use [HANDOFF.md](HANDOFF.md) for current installation, second-model commands,
CI and PR repair steps. It supersedes the original planning checklist below.

You own the wrapping: the run on your laptop, CI, generated tests, the Sweep
demo and the documents. You never need to edit `versionguard/` or
`experiment/`; if something there looks wrong, open an issue.

Your folders: `.github/`, `tests/` (new files), `docs/`, `README.md`.
Work on a branch and merge through a pull request.

## 1. Run your model (start this first; it runs unattended)

Needs Python 3.10+, Ollama and Docker Desktop.

```
git clone <repo url> && cd VersionGuard
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
ollama pull codellama:7b-instruct
python -m experiment.fetch_data
python -m experiment.doctor --model codellama:7b-instruct
python -m experiment.prepare --split test --verify-only
```

`--verify-only` builds the pinned environments and checks that the reference
solutions pass on your laptop as they did on the first one. If it reports any
mismatch, stop and send the output back; do not start the run.

```
python -m experiment.run --split dev --model codellama:7b-instruct --limit 5      # five-task check
python -m experiment.run --split test --model codellama:7b-instruct               # the full run
```

It saves after every answer. If it stops, run the same command again. When it
finishes:

```
git add results/test-codellama_7b-instruct.jsonl results/test-codellama_7b-instruct.meta.json
git commit -m "Results: CodeLlama 7B on the test split" && git push
```

Qwen is complete on the first laptop; do not repeat `qwen2.5:7b` as another
model because it has the same local digest as `qwen2.5:7b-instruct`. CodeLlama
7B is the selected approximately same-size comparison model.
Rules: one whole model per laptop, and do not change any setting.

## 2. GitHub Actions workflow

`.github/workflows/ci.yml` is implemented and needs no Ollama or Docker. Use
the checked-in workflow; the original sketch below is historical planning:

```yaml
name: ci
on:
  push: { branches: [main] }
  pull_request:
jobs:
  checks:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install -r requirements-dev.txt
      - name: Lint
        run: ruff check .
      - name: Tests with coverage
        run: |
          coverage run -m pytest -q
          coverage report
      - name: Pipeline self-check (six conditions, stand-in model)
        run: |
          python -m experiment.run --split fixtures --model fake:stale --executor host
          python -m experiment.report --split fixtures
      - name: Guard on changed Python files
        if: github.event_name == 'pull_request'
        run: |
          files=$(git diff --name-only --diff-filter=AM origin/${{ github.base_ref }}...HEAD -- '*.py')
          if [ -n "$files" ]; then python -m versionguard.check --github $files; fi
```

Then:

- Protect `main` so a pull request needs a green run.
- For the demo, open a pull request that adds a small file under `demo/` using
  a removed call (for example `np.trapz` with a `requirements-demo.txt` that
  pins `numpy>=2.4`, installed in the workflow). The guard should fail it with
  an annotation on the exact line. Fix the call, push, show it turn green.
  Screenshot both.

## 3. Generated tests (Qodo, formerly Codium)

1. Record coverage before: `coverage run -m pytest -q && coverage report`.
2. Use Qodo Gen in VS Code to generate tests for `versionguard/codeparse.py`,
   `versionguard/repair.py`, `versionguard/store.py` and `versionguard/check.py`.
3. Keep only tests that pass and that you can explain. Put them in new files
   named `tests/test_generated_*.py`.
4. Record coverage after. Note how many generated tests you kept, how many you
   threw away, and why. That table goes in the report.

## 4. Sweep

Try installing the Sweep GitHub app on the repository and open an issue titled
`Sweep: add type hints to versionguard/store.py`. If it opens a pull request,
the CI run on that pull request is the demo: an AI wrote the code and the
pipeline checked it. If Sweep cannot be installed, write down what happened
and tell your teammate the same day, so a substitute can be agreed with the
instructor.

## 5. Failure notes

After both runs are in, `python -m experiment.report --split test` already
counts failures by category. Your part: open the results file, read ten failed
answers from your model across different categories, and write two or three
sentences on each pattern you see, with one concrete example (task id, what
the model wrote, what the error was).

## 6. Documents

- Updated one-page charter and timeline (progress against plan).
- Pipeline diagram for the README.
- The 1-2 page progress report: paste the tables from `results/report-test.md`.
- Write the README section that explains the experiment in your own words;
  you will be asked to explain it.

## What to send back for the presentation

- `results/test-<your model>.jsonl` and its `.meta.json` (committed).
- Coverage before and after, with the kept/discarded count.
- Screenshots: green run, the guard failing a pull request, the Sweep pull request.
- The failure notes.
