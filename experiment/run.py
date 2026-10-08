"""Run one model through the six conditions on a split.

    python -m experiment.run --split dev  --model codellama:7b-instruct
    python -m experiment.run --split test --model codellama:7b-instruct
    python -m experiment.run --split fixtures --model fake:stale --executor host   # self-check

Results are appended to results/<split>-<model>.jsonl after every answer, so
an interrupted run loses nothing: run the same command again and it continues
where it stopped. (Resume logic ported from OmniLearn's eval/evaluate.py.)

One model = one laptop. Never split a model's conditions across machines:
every comparison between conditions must come from the same hardware.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import platform
import re
import sys
import time
from pathlib import Path
from typing import Any, Optional

from experiment.dataset import DATA_FILE, REPO_ROOT, SPLIT_FILE, retrieval_cache_path, sha256_of, tasks_for
from experiment.executor import EnvFailure, PROGRAM_NAME, make_executor
from versionguard.codeparse import NoCodeError, assemble_program, target_name
from versionguard.config import RESULTS_DIR, settings
from versionguard.llm import check_connection, make_llm
from versionguard.prompts import (
    CONDITIONS,
    REPAIR,
    REPAIR_BASE,
    USES_ORACLE_DOCS,
    USES_RETRIEVED_DOCS,
    build_prompt,
)
from versionguard.repair import Outcome, classify, sanitize_feedback
from versionguard.task import Task

PROTOCOL_FILE = REPO_ROOT / "experiment" / "PROTOCOL.md"
# If any of these differ from an existing results file, the run refuses to append.
LOCKED = ("model", "split", "temperature", "seed", "num_ctx", "num_predict", "retrieval_cache_sha256", "executor",
          "exec_timeout_s", "protocol_sha256", "dataset_sha256", "split_sha256")


def slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_") or "model"


def results_path(split: str, model: str, directory: Optional[Path] = None) -> Path:
    return Path(directory or RESULTS_DIR) / f"{split}-{slug(model)}.jsonl"


def load_records(path: Path) -> list[dict]:
    records: list[dict] = []
    if path.is_file():
        with open(path, encoding="utf-8") as stream:
            for line in stream:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
    return records


def append_record(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(record, ensure_ascii=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def run_metadata(split: str, model: str, executor_kind: str, llm: Any, cache_path: Path,
                 timeout: Optional[int] = None) -> dict:
    return {
        "model": model,
        "split": split,
        "executor": executor_kind,
        "temperature": settings.temperature,
        "seed": settings.seed,
        "num_ctx": settings.num_ctx,
        "num_predict": settings.num_predict,
        "exec_timeout_s": settings.exec_timeout_s if timeout is None else timeout,
        "dataset_sha256": sha256_of(DATA_FILE) if split != "fixtures" and DATA_FILE.is_file() else None,
        "split_sha256": sha256_of(SPLIT_FILE) if split != "fixtures" and SPLIT_FILE.is_file() else None,
        "retrieval_cache_sha256": sha256_of(cache_path) if cache_path.is_file() else None,
        "protocol_sha256": sha256_of(PROTOCOL_FILE) if PROTOCOL_FILE.is_file() else None,
        "llm": llm.describe(),
        "machine": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python": platform.python_version(),
        },
        "started_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
    }


def check_metadata(meta_path: Path, current: dict, force: bool) -> None:
    """Refuse to mix two different configurations in one results file."""
    if not meta_path.is_file():
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        meta_path.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
        return
    previous = json.loads(meta_path.read_text(encoding="utf-8"))
    # Older files lack the new data hashes; existing recorded settings still lock.
    changed = [key for key in LOCKED if key in previous and previous.get(key) != current.get(key)]
    for key in ("model_digest", "ollama_version"):
        before, after = previous.get("llm", {}).get(key), current.get("llm", {}).get(key)
        if before is not None and before != after:
            changed.append(f"llm.{key}")
    if changed and not force:
        details = ", ".join(changed)
        raise SystemExit(
            f"error: {meta_path.name} was started with different settings ({details}).\n"
            "Results from different settings must not share a file. Move the old results away, "
            "or pass --force if you are sure."
        )
    if changed:
        previous.setdefault("forced_changes", []).append({"keys": changed, "settings": current})
        meta_path.write_text(json.dumps(previous, indent=2) + "\n", encoding="utf-8")


def execute(executor: Any, task: Task, answer: str, test: str, timeout: int) -> tuple[Outcome, str, str, str, float]:
    """Run an answer against a test. Returns (outcome, code, mode, sanitized log, ms)."""
    try:
        program = assemble_program(task.starting_code, answer, test)
    except NoCodeError as exc:
        name = target_name(task.starting_code) or "the function"
        feedback = f"Your previous answer did not contain a complete Python definition of {name}."
        return Outcome("no_code", "NoCode", "no_code", str(exc)), "", "", feedback, 0.0
    result = executor.run(task, program.source, timeout)
    outcome = classify(result.returncode, result.stderr, result.timed_out)
    if outcome.passed:
        feedback = ""
    elif result.timed_out:
        feedback = f"The program did not finish within {timeout} seconds."
    else:
        feedback = sanitize_feedback(result.stderr, program.candidate_lines, PROGRAM_NAME)
    return outcome, program.candidate, program.mode, feedback, round(result.duration_ms, 1)


def run_condition(
    condition: str,
    task: Task,
    llm: Any,
    executor: Any,
    docs: dict,
    base: Optional[dict],
    timeout: int,
) -> dict:
    """One (task, condition) cell. Returns the fields to record."""
    fields: dict[str, Any] = {"carried": False, "docs_shown": []}

    docs_text = None
    if condition in USES_RETRIEVED_DOCS:
        docs_text = docs.get("retrieved_text") or ""
        fields["docs_shown"] = [d["qualname"] for d in docs.get("retrieved", [])]
        if not docs_text:
            return {**fields, "status": "skipped", "category": "no_docs", "passed": None,
                    "error_message": "lookup returned no documentation"}
    elif condition in USES_ORACLE_DOCS:
        if not docs.get("oracle_available"):
            return {**fields, "status": "skipped", "category": "no_oracle", "passed": None,
                    "error_message": "reference APIs could not be matched to documentation"}
        docs_text = docs["oracle_text"]
        fields["docs_shown"] = [d["qualname"] for d in docs["oracle"]]

    previous_code = feedback = None
    if condition in REPAIR:
        if base is None:
            raise SystemExit(
                f"error: condition '{condition}' needs the '{REPAIR_BASE}' result for task "
                f"{task.example_id} first. Run without --conditions, or include '{REPAIR_BASE}'."
            )
        if base.get("passed"):
            # Nothing to repair: the first attempt already passed and is kept.
            return {**fields, "carried": True, "status": "pass", "passed": True, "category": "",
                    "error_type": "", "error_message": "", "code": base.get("code", ""),
                    "answer": "", "latency_ms": 0.0, "input_tokens": 0, "output_tokens": 0}
        if base.get("status") in ("env_error", "skipped"):
            return {**fields, "status": "skipped", "category": "no_base", "passed": None,
                    "error_message": "the first attempt could not be run"}
        previous_code = base.get("code") or (base.get("answer") or "")[:2000]
        feedback = base.get("feedback") or "The program failed."

    system, user = build_prompt(condition, task, docs_text, previous_code, feedback)
    result = llm.generate(system, user, task=task, condition=condition)
    try:
        outcome, code, mode, log, exec_ms = execute(executor, task, result.text, task.test, timeout)
        # Feedback for a later repair comes from the visible test when the
        # benchmark provides one, so the hidden test never reaches the model.
        if not outcome.passed and task.visible_test and code:
            _o, _c, _m, log, _ms = execute(executor, task, result.text, task.visible_test, timeout)
    except EnvFailure as exc:
        return {**fields, "status": "env_error", "category": "env_error", "passed": None,
                "error_message": str(exc)[:300], "answer": result.text}
    return {
        **fields,
        "status": outcome.status,
        "passed": outcome.passed,
        "category": outcome.category,
        "error_type": outcome.error_type,
        "error_message": outcome.message,
        "answer_mode": mode,
        "code": code,
        "answer": result.text,
        "feedback": log,
        "latency_ms": result.latency_ms,
        "exec_ms": exec_ms,
        "input_tokens": result.metrics.get("input_tokens"),
        "output_tokens": result.metrics.get("output_tokens"),
        "prompt_chars": len(system) + len(user),
    }


def run(args: argparse.Namespace) -> Path:
    model = args.model or settings.ollama_model
    conditions = list(args.conditions or CONDITIONS)
    unknown = [c for c in conditions if c not in CONDITIONS]
    if unknown:
        raise SystemExit(f"error: unknown condition(s): {', '.join(unknown)}")
    # Keep the canonical order so a repair always follows its first attempt.
    conditions = [c for c in CONDITIONS if c in conditions]

    tasks = tasks_for(args.split)
    cache_path = retrieval_cache_path(args.split)
    if not cache_path.is_file():
        raise SystemExit(f"error: {cache_path} not found. Run: python -m experiment.prepare --split {args.split}")
    cache = json.loads(cache_path.read_text(encoding="utf-8"))
    prepared = cache.get("tasks", {})
    missing = [t.example_id for t in tasks if t.example_id not in prepared]
    if missing:
        raise SystemExit(f"error: preparation is incomplete for {len(missing)} {args.split} task(s). "
                         f"Run: python -m experiment.prepare --split {args.split}")
    mismatched = [t.example_id for t in tasks if prepared[t.example_id].get("env_key") != t.env_key]
    if mismatched:
        raise SystemExit("error: lookup cache environments differ from the selected tasks. Rebuild preparation.")
    usable = [t for t in tasks if prepared.get(t.example_id, {}).get("usable")]
    skipped = len(tasks) - len(usable)
    if args.limit:
        usable = usable[: args.limit]
    if not usable:
        raise SystemExit(f"error: no prepared tasks for split '{args.split}'. Run experiment.prepare first.")

    llm = make_llm(model)
    if not model.startswith("fake:"):
        status = check_connection(model=model)
        if not status["connected"]:
            raise SystemExit(f"error: Ollama is not reachable at {status['base_url']}: {status.get('error')}")
        if not status["is_configured_model_available"]:
            raise SystemExit(f"error: model '{model}' is not pulled. Run: ollama pull {model}")
    executor = make_executor(args.executor)
    if args.executor == "docker":
        available, detail = executor.available()
        if not available:
            raise SystemExit(f"error: Docker is not usable ({detail}). Start Docker Desktop and try again.")
    elif args.split != "fixtures":
        raise SystemExit("error: real benchmark tasks require --executor docker; --executor host is for fixtures only.")

    path = results_path(args.split, model, args.results_dir)
    meta_path = path.with_suffix(".meta.json")
    check_metadata(meta_path, run_metadata(args.split, model, args.executor, llm, cache_path, args.timeout), args.force)

    existing = {(r["example_id"], r["condition"]): r for r in load_records(path)}
    total = len(usable) * len(conditions)
    print(f"Model: {model}   split: {args.split}   executor: {args.executor}")
    print(f"Tasks: {len(usable)} usable ({skipped} not prepared or unusable)   conditions: {', '.join(conditions)}")
    print(f"Planned: {total} runs   already done: {sum(1 for t in usable for c in conditions if (t.example_id, c) in existing)}")
    print(f"Results: {path}\n")

    started = time.perf_counter()
    position = 0
    for task in usable:
        docs = prepared[task.example_id]
        for condition in conditions:
            position += 1
            key = (task.example_id, condition)
            if key in existing:
                continue
            cell_start = time.perf_counter()
            base = existing.get((task.example_id, REPAIR_BASE)) if condition in REPAIR else None
            fields = run_condition(condition, task, llm, executor, docs, base, args.timeout)
            record = {
                "run_id": f"{args.split}-{slug(model)}-{task.example_id}-{condition}",
                "model": model,
                "split": args.split,
                "condition": condition,
                "example_id": task.example_id,
                "library": task.library,
                "version": task.version,
                "python_version": task.python_version,
                "type_of_change": task.type_of_change,
                "retrieval_hit": docs.get("retrieval_hit"),
                "oracle_available": docs.get("oracle_available"),
                **fields,
                "finished_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            }
            append_record(path, record)
            existing[key] = record
            took = time.perf_counter() - cell_start
            elapsed = (time.perf_counter() - started) / 60
            note = " (kept first attempt)" if record.get("carried") else ""
            print(
                f"Run {position}/{total} | task {task.example_id} | {condition:<11} | "
                f"{record['status']}{note} | {took:.1f}s | elapsed {elapsed:.1f}m",
                flush=True,
            )

    print(f"\nFinished in {(time.perf_counter() - started) / 60:.1f} min. Results: {path}")
    print(f"Next: python -m experiment.report --split {args.split}")
    return path


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("--split", required=True, choices=["fixtures", "dev", "test"])
    parser.add_argument("--model", help="Ollama model tag, or fake:reference / fake:stale for the self-check")
    parser.add_argument("--conditions", nargs="+", help=f"subset of: {' '.join(CONDITIONS)}")
    parser.add_argument("--executor", default="docker", choices=["docker", "host"])
    parser.add_argument("--limit", type=positive_int, help="only the first N tasks (use 5 for the quick check)")
    parser.add_argument("--timeout", type=positive_int, default=settings.exec_timeout_s, help="seconds per test run")
    parser.add_argument("--results-dir", help="where to write results (default: results/)")
    parser.add_argument("--force", action="store_true", help="append even if the settings changed")
    return parser.parse_args(argv)


def positive_int(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return number


def main(argv: Optional[list[str]] = None) -> int:
    try:
        run(parse_args(argv))
    except (RuntimeError, OSError, ValueError) as exc:
        print(f"error: {exc}\nCompleted results are saved. Fix the runtime issue and repeat the same command to resume.",
              file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\nInterrupted. Completed results are saved; repeat the same command to resume.", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
