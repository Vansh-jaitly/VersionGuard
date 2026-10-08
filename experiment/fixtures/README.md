# Self-check fixtures (not experiment data)

`minilib` is a tiny made-up library in two versions (`libs/minilib-1.0`,
`libs/minilib-2.0`). `tasks.jsonl` holds six hand-written tasks in the same
format as the benchmark, each with a `stale_solution` written for the other
version.

They exist so the whole pipeline (documentation extraction, lookup, the six
conditions, repair, the guard, the report) can run in seconds with no Ollama,
no Docker and no downloads: on a laptop, and in GitHub Actions.

Results produced from these fixtures with a `fake:` model are a plumbing
check. They say nothing about any real model and must never be reported as
findings.
