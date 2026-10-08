"""Get a split ready to run: environments, reference check, documentation, lookup.

    python -m experiment.prepare --split dev
    python -m experiment.prepare --split test
    python -m experiment.prepare --split fixtures --executor host --retriever bm25

For every task in the split this
  1. builds the pinned environment (once per environment),
  2. runs the benchmark's own reference solution; a task whose reference does
     not pass in our environment is marked unusable and never shown to a model,
  3. reads the documentation entries out of the installed libraries,
  4. looks up the top-k entries for the task and records them.

Step 4 is written to experiment/retrieval_cache.json, which is committed. The
runner reads documentation only from that file, so both laptops show every
model exactly the same documentation, and a results file can name the cache
it used.

This is the slow, one-off step (it downloads Python images and libraries).
It makes no model calls. Run it on one laptop and commit the cache.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Optional, Sequence

from experiment.dataset import load_split_file, retrieval_cache_path, tasks_for
from experiment.executor import EnvFailure, make_executor
from versionguard.codeparse import reference_program
from versionguard.config import APIDOCS_DIR, settings
from versionguard.repair import classify
from versionguard.store import ApiDoc, corpus_fingerprint, format_docs, get_retriever, load_api_docs
from versionguard.task import Task

MAX_ORACLE_DOCS = 3
# Bump when the way entries are chosen changes, so old caches are rebuilt.
LOOKUP_VERSION = "one-entry-per-name-v1"


def lookup_query(task: Task) -> str:
    """What the lookup searches with: the task text and the code to complete."""
    return f"{task.problem}\n{task.starting_code}"


def resolve_oracle(task: Task, docs: Sequence[ApiDoc]) -> list[ApiDoc]:
    """Documentation entries for the APIs the reference solution calls.

    A reference call such as `scipy.stats.norm.logcdf` is matched exactly if
    there is such an entry, otherwise by its longest dotted prefix that is an
    entry (`scipy.stats.norm`). Calls on local variables (`df.append`) cannot
    be matched and are ignored; if nothing matches, the task has no oracle.
    """
    by_name = {doc.qualname: doc for doc in docs}
    found: list[ApiDoc] = []
    for call in task.api_calls:
        parts = call.split(".")
        for size in range(len(parts), 1, -1):
            doc = by_name.get(".".join(parts[:size]))
            if doc is not None:
                if doc not in found:
                    found.append(doc)
                break
    return found[:MAX_ORACLE_DOCS]


def _entry(doc: ApiDoc) -> dict:
    return {"qualname": doc.qualname, "text": doc.text}


def prepare(split: str, executor_kind: str, retriever_kind: str, k: int, limit: Optional[int]) -> dict:
    tasks = tasks_for(split)
    if limit:
        tasks = tasks[:limit]
    executor = make_executor(executor_kind)
    cache_path = retrieval_cache_path(split)
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.is_file() else {}
    if cache.get("retriever") not in (None, retriever_kind) or cache.get("k") not in (None, k):
        print("note: lookup settings changed; rebuilding the cache from scratch")
        cache = {}
    if cache.get("lookup_version") not in (None, LOOKUP_VERSION):
        print("note: the lookup method changed; rebuilding the cache from scratch")
        cache = {}
    cache.update({"retriever": retriever_kind, "k": k, "doc_char_budget": settings.doc_char_budget,
                  "lookup_version": LOOKUP_VERSION})
    if retriever_kind == "vector":
        cache["embedding_model"] = settings.embedding_model
    entries: dict = cache.setdefault("tasks", {})
    if split != "fixtures":
        # A re-selected split must not leave old tasks behind in the cache.
        current = set(load_split_file()["dev"]) | set(load_split_file()["test"])
        for stale in [key for key in entries if key not in current]:
            del entries[stale]

    retrievers: dict[str, object] = {}
    corpora: dict[str, list[ApiDoc]] = {}
    started = time.perf_counter()
    for index, task in enumerate(tasks, 1):
        label = f"[{index}/{len(tasks)}] {task.example_id} {task.library}=={task.version}"
        record: dict = {"env_key": task.env_key, "split": split}
        try:
            executor.ensure(task)
            reference = reference_program(task.starting_code, task.solution, task.test)
            outcome_raw = executor.run(task, reference.source)
            outcome = classify(outcome_raw.returncode, outcome_raw.stderr, outcome_raw.timed_out)
            if not outcome.passed:
                record.update(usable=False, reason=f"reference solution: {outcome.status} {outcome.error_type} {outcome.message}".strip())
                entries[task.example_id] = record
                print(f"{label}  UNUSABLE ({record['reason'][:90]})", flush=True)
                continue

            if task.env_key not in corpora:
                docs_path = APIDOCS_DIR / f"{task.env_key}.jsonl"
                if not docs_path.is_file():
                    executor.extract_docs(task, docs_path)
                corpora[task.env_key] = load_api_docs(docs_path)
                retrievers[task.env_key] = get_retriever(corpora[task.env_key], task.env_key, retriever_kind)
            docs = corpora[task.env_key]
            hits = retrievers[task.env_key].search(lookup_query(task), k)  # type: ignore[attr-defined]
            retrieved = [doc for doc, _score in hits]
            oracle = resolve_oracle(task, docs)
            oracle_names = {doc.qualname for doc in oracle}
            record.update(
                usable=True,
                corpus_size=len(docs),
                corpus_fingerprint=corpus_fingerprint(docs),
                retrieved=[_entry(doc) for doc in retrieved],
                retrieved_text=format_docs(retrieved),
                oracle=[_entry(doc) for doc in oracle],
                oracle_text=format_docs(oracle) if oracle else "",
                oracle_available=bool(oracle),
                retrieval_hit=(any(doc.qualname in oracle_names for doc in retrieved) if oracle else None),
            )
            entries[task.example_id] = record
            hit = {True: "hit", False: "miss", None: "no oracle"}[record["retrieval_hit"]]
            print(f"{label}  ok  docs={len(docs)}  lookup={hit}", flush=True)
        except EnvFailure as exc:
            record.update(usable=False, reason=f"environment: {str(exc)[:300]}")
            entries[task.example_id] = record
            print(f"{label}  UNUSABLE (environment)\n    {str(exc)[:300]}", flush=True)
        finally:
            # Includes failed references, which continue out of the try block.
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = cache_path.with_suffix(cache_path.suffix + ".tmp")
            with open(temporary, "w", encoding="utf-8", newline="\n") as stream:
                stream.write(json.dumps(cache, indent=1, ensure_ascii=False) + "\n")
            temporary.replace(cache_path)

    done = [entries[t.example_id] for t in tasks if t.example_id in entries]
    usable = [r for r in done if r.get("usable")]
    with_oracle = [r for r in usable if r.get("oracle_available")]
    hits = [r for r in with_oracle if r.get("retrieval_hit")]
    minutes = (time.perf_counter() - started) / 60
    print(
        f"\n{split}: {len(usable)}/{len(done)} tasks usable, "
        f"{len(with_oracle)} with an oracle, lookup found the reference API for "
        f"{len(hits)}/{len(with_oracle)} of those. ({minutes:.1f} min)"
    )
    print(f"Wrote {cache_path}")
    return cache


def verify(split: str, executor_kind: str, limit: Optional[int]) -> int:
    """Second laptop: build the environments and confirm the reference solutions
    behave here as they did where the cache was made. Changes nothing."""
    cache_path = retrieval_cache_path(split)
    if not cache_path.is_file():
        print(f"error: {cache_path} not found (it should come with the repository)", file=sys.stderr)
        return 1
    entries = json.loads(cache_path.read_text(encoding="utf-8")).get("tasks", {})
    selected = tasks_for(split)
    missing = [task.example_id for task in selected if task.example_id not in entries]
    if missing:
        print(f"error: preparation is incomplete for {len(missing)} selected tasks; obtain the completed lookup cache.",
              file=sys.stderr)
        return 1
    tasks = [t for t in selected if entries[t.example_id].get("usable")]
    if not tasks:
        print("error: no usable reference solutions in the lookup cache", file=sys.stderr)
        return 1
    if limit:
        tasks = tasks[:limit]
    executor = make_executor(executor_kind)
    mismatches = 0
    for index, task in enumerate(tasks, 1):
        label = f"[{index}/{len(tasks)}] {task.example_id} {task.library}=={task.version}"
        try:
            reference = reference_program(task.starting_code, task.solution, task.test)
            raw = executor.run(task, reference.source)
            outcome = classify(raw.returncode, raw.stderr, raw.timed_out)
            state = "ok" if outcome.passed else f"MISMATCH ({outcome.status} {outcome.error_type})"
        except EnvFailure as exc:
            state = f"MISMATCH (environment: {str(exc)[:160]})"
        mismatches += state != "ok"
        print(f"{label}  {state}", flush=True)
    print(f"\n{len(tasks) - mismatches}/{len(tasks)} reference solutions pass on this laptop.")
    if mismatches:
        print("Do not start the full run: this laptop's environments differ. Send this output to your teammate.")
    return 1 if mismatches else 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("--verify-only", action="store_true",
                        help="second laptop: check the environments against the committed cache, change nothing")
    parser.add_argument("--split", required=True, choices=["fixtures", "dev", "test", "all"])
    parser.add_argument("--executor", default="docker", choices=["docker", "host"])
    parser.add_argument("--retriever", default=settings.retriever_kind, choices=["vector", "bm25"])
    parser.add_argument("--k", type=int, default=settings.retriever_k)
    parser.add_argument("--limit", type=int, help="only the first N tasks (for a quick check)")
    args = parser.parse_args(argv)
    try:
        if args.verify_only:
            return verify(args.split, args.executor, args.limit)
        prepare(args.split, args.executor, args.retriever, args.k, args.limit)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
