"""Check that this laptop is ready, before a long run.

    python -m experiment.doctor                       # tools only
    python -m experiment.doctor --model llama3.2:3b   # also check the model is pulled
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
from typing import Optional

from experiment.dataset import DATA_FILE, RETRIEVAL_CACHE, SPLIT_FILE, sha256_of
from experiment.executor import DockerExecutor
from versionguard.config import settings
from versionguard.llm import check_connection

OK, BAD, SKIP = "OK  ", "FAIL", "--  "


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("--model", default=settings.ollama_model)
    args = parser.parse_args(argv)
    problems = 0

    def line(state: str, name: str, detail: str = "") -> None:
        nonlocal problems
        problems += state == BAD
        print(f"[{state}] {name:<22} {detail}")

    version = sys.version_info
    line(OK if version >= (3, 10) else BAD, "Python", f"{platform.python_version()} (need 3.10+)")
    line(OK, "Laptop", f"{platform.system()} {platform.machine()}")

    status = check_connection(model=args.model)
    if not status["connected"]:
        line(BAD, "Ollama", f"not reachable at {status['base_url']} - start Ollama")
    else:
        line(OK, "Ollama", f"version {status.get('ollama_version')}")
        if status["is_configured_model_available"]:
            line(OK, "Model", f"{args.model} (digest {(status.get('configured_model_digest') or '')[:12]})")
        else:
            line(BAD, "Model", f"{args.model} not pulled - run: ollama pull {args.model}")

    available, detail = DockerExecutor.available()
    line(OK if available else BAD, "Docker", f"server {detail}" if available else f"{detail} - start Docker Desktop")

    for label, module in (("LangChain + Ollama", "langchain_ollama"), ("LangChain + Chroma", "langchain_chroma"),
                          ("Embeddings", "langchain_huggingface")):
        try:
            __import__(module)
            line(OK, label, module)
        except Exception as exc:  # noqa: BLE001
            if label == "LangChain + Ollama":
                line(SKIP, label, f"{module} not importable ({type(exc).__name__}) - using Ollama HTTP fallback")
            else:
                line(SKIP, label, f"{module} not importable ({type(exc).__name__})"
                     " - only needed to rebuild the lookup cache")

    if DATA_FILE.is_file():
        line(OK, "Benchmark data", f"{DATA_FILE.name} sha256 {sha256_of(DATA_FILE)[:12]}")
    else:
        line(BAD, "Benchmark data", "missing - run: python -m experiment.fetch_data")
    if SPLIT_FILE.is_file():
        spec = json.loads(SPLIT_FILE.read_text(encoding="utf-8"))
        match = DATA_FILE.is_file() and spec.get("dataset_sha256") == sha256_of(DATA_FILE)
        note = "" if match else " - the data file differs from the one the split was made from"
        line(OK if match else BAD, "Task split", f"dev {len(spec['dev'])}, test {len(spec['test'])}{note}")
    else:
        line(BAD, "Task split", "missing - run: python -m experiment.select_tasks")
    if RETRIEVAL_CACHE.is_file():
        cache = json.loads(RETRIEVAL_CACHE.read_text(encoding="utf-8"))
        cached_tasks = cache.get("tasks", {})
        expected = set()
        if SPLIT_FILE.is_file():
            spec = json.loads(SPLIT_FILE.read_text(encoding="utf-8"))
            expected = set(spec.get("dev", [])) | set(spec.get("test", []))
        usable_ids = {task_id for task_id, task in cached_tasks.items() if task.get("usable")}
        missing = expected - usable_ids
        coverage = (f"{len(expected) - len(missing)}/{len(expected)} selected tasks usable"
                    if expected else f"{len(usable_ids)} usable tasks")
        detail = f"{coverage}, sha256 {sha256_of(RETRIEVAL_CACHE)[:12]}"
        if missing:
            detail += f" - prepare is incomplete (missing/unusable {len(missing)})"
        line(BAD if missing else OK, "Lookup cache", detail)
    else:
        line(BAD, "Lookup cache", "missing - run: python -m experiment.prepare --split dev (then test)")

    print("\nReady." if not problems else f"\n{problems} thing(s) to fix before a real run.")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
