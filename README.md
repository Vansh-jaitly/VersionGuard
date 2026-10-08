# VersionGuard

AI models write code for library versions they remember, not the version a
project has installed. VersionGuard looks documentation up for the **pinned**
version before the model writes code, checks pull requests for calls that do
not exist in that version, and measures whether any of this helps.

| Part | Command | What it does |
|---|---|---|
| Bot | `python -m versionguard.ask "question" --library numpy` | Looks up documentation for the installed version, then asks a local model |
| Guard | `python -m versionguard.check path/` | Flags calls and arguments that do not exist in the installed versions |
| Experiment | `python -m experiment.run --split test --model <tag>` | Six conditions, scored by the benchmark's tests |

These three commands are the contract: the CI workflow, the demo and the
report only ever call them.

## Research question

Does looking up documentation for the pinned library version make code written
by a small local model pass more tests than the model alone, on the first
attempt and when repairing a failed attempt? The conditions, fixed settings and
the pass/fail rule are in [`experiment/PROTOCOL.md`](experiment/PROTOCOL.md),
written before any test run.

| # | Condition | The model is given |
|---|---|---|
| 1 | Task only | the task |
| 2 | Version | the task and the pinned versions |
| 3 | Lookup | 2 plus documentation found by the lookup |
| 4 | Correct docs | 2 plus documentation of the APIs the reference solution uses |
| 5 | Repair, log only | 2, the failed code from 2, and its error log |
| 6 | Repair, log + docs | 5 plus the documentation from 3 |

## Current build status

Source is hosted at [Vansh-jaitly/VersionGuard](https://github.com/Vansh-jaitly/VersionGuard).
Baseline Actions and the corrected demo PR are green; the earlier red PR and
actual Qwen repair comment are preserved. See [live evidence](docs/LIVE_EVIDENCE.md).
Named-tool rubric gaps remain: Qodo Command returned a discontinued-service
notice, and legacy Sweep GitHub app access was not established. The teammate's
CodeLlama evaluation is returned and [audited](docs/TEAMMATE_INTAKE.md).

The Qwen evaluation is complete on this Windows laptop using
`qwen2.5:7b-instruct` and real Docker environments: 20 development tasks
(120 condition records, 12.2 minutes) and 40 held-out test tasks
(240 condition records, 26.2 minutes). Preparation, reference checks and the
cached vector lookup cover all 60 selected tasks.

The [test report](results/report-test.md) records 45.0% passing with version
information and 52.5% with lookup. The gain is 7.5 points, with a 95% interval
of [-7.5, +22.5], so it does not meet the registered success rule. Repair with
logs and repair with logs plus documentation both pass 55.0%. There are 18
legitimate skipped oracle cells because reference API documentation could not
be matched. These skips are recorded, not counted as model failures.

CodeLlama's independent Mac run also covers 40 test tasks and 240 records.
Documentation-assisted repair improves from 42.5% to 65.0% (+22.5 points;
95% interval [+10.0, +35.0]), meeting the registered within-model rule. All
nine repair gains were independently replayed in Docker. Its
[standalone report](results/incoming/codellama-mac/report-test.md) passes strict
validation. The [combined report](results/model-comparison/report-test.md)
remains provisional because CodeLlama used Ollama 0.32.15 and Qwen used 0.35.0.

Validation: 92 tests and 2 subtests pass, lint passes, and core coverage is
69%. A standalone repair of `np.asscalar` to `array.item()` also passes in
Docker with NumPy 1.25.0; the initial hallucinated `np.item` proposal and its
failure are preserved in [demo verification](results/repair-demo-verification.json).
This demonstration is separate from the benchmark.

GitHub CI, a local guard demo, PR repair comment preview/posting, validated
second-model result import and teammate ZIP packaging are implemented.
Hosted Actions, the red/green PR demonstration and the second laptop's model run
are complete. The runtime comparison limitation, named-tool rubric evidence and student
presentation remain pending; actual tool limitations are documented.
See [build status and handoff](experiment/BUILD_STATUS.md).
Local integration evidence is in [integration verification](results/integration-validation.md).

## Integration and teammate delivery

Current mid-term work: [completion workflow](docs/COMPLETION_WORKFLOW.md),
[charter](docs/CHARTER.md), [timeline](docs/TIMELINE.md),
[brief progress report](docs/PROGRESS_REPORT.md) and [demo guide](docs/DEMO_GUIDE.md).
The teammate's [evaluation-only scope](docs/EVALUATION_ONLY.md) has been delivered;
the [intake report](docs/TEAMMATE_INTAKE.md) records acceptance and limitations.
The current shared completion steps are in [finish together](docs/FINISH_TOGETHER.md).
Run all local integration checks with `.venv\Scripts\python.exe -m scripts.verify`.

See [teammate handoff](docs/HANDOFF.md) for the workflow, PR repair command,
second-model instructions and evidence checklist. Build or verify the archive:

```powershell
python -m scripts.teammate_bundle
python -m scripts.teammate_bundle --verify deliverables/VersionGuard-teammate.zip
```

The ZIP includes the frozen dataset/cache and Qwen evidence with per-file
checksums. CI uses the fixture model; PR repair uses local Ollama and saves a
preview unless explicitly invoked with `--post`.

## Setup

Needs Python 3.10+, [Ollama](https://ollama.com) and Docker Desktop.

```
python -m venv .venv
.venv\Scripts\activate            (Windows)      source .venv/bin/activate   (macOS)
pip install -r requirements.txt -r requirements-dev.txt
pip install -r requirements-lookup.txt          (only on the laptop that builds the lookup cache)
ollama pull qwen2.5:7b-instruct                 (skip if already installed)
```

The Ollama wrapper uses LangChain when those packages are installed. If a
machine cannot install optional packages, it falls back to Ollama's local
`/api/chat` endpoint with the same fixed generation settings.

## The experiment, step by step

Steps 1 to 4 are done once, on one laptop, and their outputs are committed.

```
1. python -m experiment.fetch_data                      download the benchmark tasks
2. python -m experiment.select_tasks --list             see what is available
   python -m experiment.select_tasks                    choose 60 tasks, split 20 dev / 40 test
3. python -m experiment.prepare --split dev             build environments, check references,
   python -m experiment.prepare --split test            extract documentation, cache the lookup
4. git add experiment/splits/split.json experiment/retrieval_cache.json && git commit

5. python -m experiment.doctor --model <tag>            is this laptop ready?
6. python -m experiment.run --split dev --model <tag> --limit 5     five-task check
7. python -m experiment.run --split dev --model <tag>               tune on dev only
8. python -m experiment.run --split test --model <tag>              once, when everything is fixed
9. python -m experiment.report --split test             tables with confidence intervals
```

A run saves after every answer. If it stops, run the same command again and it
continues. One model runs entirely on one laptop.

Real benchmark runs require Docker and a complete preparation cache. Resume
checks reject changed model or experiment settings. Reports can filter a model
with `--model <tag>` and require all six cells per task with `--require-complete`.

On a second laptop, skip steps 1 to 4 except `fetch_data`, then:

```
python -m experiment.prepare --split test --verify-only     same environments as the first laptop?
python -m experiment.run --split test --model <tag>
git add results/test-*.jsonl results/test-*.meta.json && git commit
```

## Repair a failed program

The bot defaults to `qwen2.5:7b-instruct`. Supply both the source file and the
error log to propose a repair:

```powershell
python -m versionguard.ask "Repair the scalar conversion" --library numpy --code broken.py --error-log build.log
```

Use `--version <version> --docs <entries.jsonl>` for documentation extracted
from a different environment. The command returns a proposal and does not
modify or execute the original program. Static findings are included in JSON
output with `--json`; detected errors return exit code 1. Static checking is
available when the installed library matches the requested version, otherwise
the answer explicitly reports `not_checked`. A clean static check does not
prove that a program passes tests; test generated code in the pinned Docker
environment.

## Self-check (no Ollama, no Docker, a few seconds)

```
python -m unittest discover -s tests -t .
python -m experiment.run --split fixtures --model fake:stale --executor host
python -m experiment.report --split fixtures
```

This uses a made-up two-version library in `experiment/fixtures` and a scripted
stand-in model. It proves the plumbing; its numbers are not results.

## Layout

```
versionguard/      the tool
  llm.py           Ollama through LangChain (ported from OmniLearn)
  apidocs.py       reads documentation out of an installed library
  store.py         lookup: Chroma + embeddings, or keyword search
  prompts.py       the six conditions as prompts
  codeparse.py     turns a model's answer into a runnable program
  repair.py        failure categories; error log made safe to show the model
  check.py         the guard
  bot.py, ask.py   the interactive bot
experiment/        the study
  PROTOCOL.md      research question, conditions, decision rule
  fetch_data.py, select_tasks.py, prepare.py, run.py, report.py, doctor.py
  executor.py      pinned environments in Docker
  fixtures/        self-check tasks and the made-up library
tests/             unit and end-to-end tests
results/           one results file per model, plus the report
docs/TEAMMATE.md   the second person's task list
```

## Credits

- Tasks and tests: **GitChameleon 2.0** (arXiv:2507.12367),
  https://github.com/mrcabbage972/GitChameleonBenchmark. Only the data is
  used; the runner, lookup, guard and statistics here are our own. The paper
  already studied lookup and retry with large hosted models; this project asks
  the question for small local models and adds the guard and the
  log-versus-documentation repair comparison.
- `versionguard/llm.py` and the resume logic in `experiment/run.py` are ported
  from the OmniLearn project.

## Known limits

- The guard follows names, not values: `df.append(...)` on a variable is
  invisible to it; `pd.DataFrame.append` is not.
- Documentation comes from the installed library, so it can say what exists,
  not what was removed.
- See "Known limits" in `experiment/PROTOCOL.md` for the experiment's own.
