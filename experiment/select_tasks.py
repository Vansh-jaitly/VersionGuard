"""Choose which benchmark tasks the experiment uses, and split them dev/test.

    python -m experiment.select_tasks --list                 # just show what is available
    python -m experiment.select_tasks                        # automatic choice
    python -m experiment.select_tasks --libraries numpy pandas flask

The choice is written to experiment/splits/split.json together with the
dataset hash and the seed, and that file is committed. Do this ONCE, before
any model is run on the test split.

Automatic choice: libraries with the most tasks first, skipping ones that are
very large to install, until the target number of tasks is reached.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter, defaultdict
from typing import Optional

from experiment.dataset import DATA_FILE, SPLIT_FILE, load_tasks, sha256_of
from versionguard.task import Task

# Each of these adds gigabytes of images for a handful of tasks.
HEAVY = {
    "torch", "torchvision", "torchaudio", "tensorflow", "jax", "jaxlib", "mxnet", "paddlepaddle",
    "transformers", "spacy", "lightgbm", "xgboost", "gradio", "librosa", "kymatio", "geopandas",
}


def summarize(tasks: list[Task]) -> str:
    by_library: dict[str, list[Task]] = defaultdict(list)
    for task in tasks:
        by_library[task.library].append(task)
    lines = [f"{'library':<18}{'tasks':>6}{'envs':>6}  python   heavy"]
    for library, items in sorted(by_library.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        environments = len({t.env_key for t in items})
        pythons = ",".join(sorted({t.python_version for t in items}))
        lines.append(
            f"{library:<18}{len(items):>6}{environments:>6}  {pythons:<8} {'yes' if library in HEAVY else ''}"
        )
    return "\n".join(lines)


def choose_libraries(tasks: list[Task], target: int) -> list[str]:
    counts = Counter(task.library for task in tasks if task.library not in HEAVY)
    chosen: list[str] = []
    total = 0
    for library, count in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        if total >= target:
            break
        chosen.append(library)
        total += count
    return chosen


def split_tasks(tasks: list[Task], total: int, dev: int, seed: int) -> tuple[list[str], list[str]]:
    """Seeded, stratified by library: every library appears in both parts."""
    rng = random.Random(seed)
    by_library: dict[str, list[Task]] = defaultdict(list)
    for task in sorted(tasks, key=lambda t: (len(t.example_id), t.example_id)):
        by_library[task.library].append(task)
    for items in by_library.values():
        rng.shuffle(items)

    # Round-robin across libraries so a cap on the total keeps the mix.
    picked: list[Task] = []
    queues = {library: list(items) for library, items in sorted(by_library.items())}
    while len(picked) < total and any(queues.values()):
        for library in sorted(queues):
            if queues[library] and len(picked) < total:
                picked.append(queues[library].pop(0))

    dev_share = dev / max(1, len(picked))
    dev_ids: list[str] = []
    test_ids: list[str] = []
    grouped: dict[str, list[Task]] = defaultdict(list)
    for task in picked:
        grouped[task.library].append(task)
    for library in sorted(grouped):
        items = grouped[library]
        cut = max(1, round(len(items) * dev_share)) if len(items) > 1 else 0
        dev_ids.extend(t.example_id for t in items[:cut])
        test_ids.extend(t.example_id for t in items[cut:])
    return dev_ids, test_ids


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("--list", action="store_true", help="show the available tasks and exit")
    parser.add_argument("--libraries", nargs="+", help="use exactly these libraries")
    parser.add_argument("--skip", nargs="+", default=[], metavar="LIB==VERSION",
                        help="leave out a pinned version that cannot be installed, e.g. numpy==1.21.0")
    parser.add_argument("--skip-reason", default="no prebuilt package for the task's Python version",
                        help="recorded in split.json next to the skipped versions")
    parser.add_argument("--total", type=int, default=60, help="number of tasks to use (default 60)")
    parser.add_argument("--dev", type=int, default=20, help="how many of them are for tuning (default 20)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--force", action="store_true", help="overwrite an existing split")
    args = parser.parse_args(argv)

    tasks = load_tasks()
    print(f"{len(tasks)} tasks in {DATA_FILE.name}\n")
    print(summarize(tasks))
    if args.list:
        return 0

    if SPLIT_FILE.exists() and not args.force:
        print(f"\nerror: {SPLIT_FILE} already exists. The split is fixed before the test run;", file=sys.stderr)
        print("use --force only if no model has been run on the test split yet.", file=sys.stderr)
        return 1

    libraries = args.libraries or choose_libraries(tasks, args.total)
    known = {task.library for task in tasks}
    unknown = [name for name in libraries if name not in known]
    if unknown:
        print(f"\nerror: not in the dataset: {', '.join(unknown)}", file=sys.stderr)
        return 1
    skipped = set(args.skip)
    bad_skip = [item for item in skipped if "==" not in item]
    if bad_skip:
        print(f"\nerror: --skip expects library==version, got: {', '.join(bad_skip)}", file=sys.stderr)
        return 1
    pool = [task for task in tasks if task.library in libraries and f"{task.library}=={task.version}" not in skipped]
    left_out = sum(1 for task in tasks if task.library in libraries) - len(pool)
    dev_ids, test_ids = split_tasks(pool, args.total, args.dev, args.seed)

    spec = {
        "dataset_file": DATA_FILE.name,
        "dataset_sha256": sha256_of(DATA_FILE),
        "seed": args.seed,
        "libraries": sorted(libraries),
        "selection": "manual" if args.libraries else "automatic (most tasks first, heavy libraries skipped)",
        "skipped_versions": sorted(skipped),
        "skipped_reason": args.skip_reason if skipped else "",
        "skipped_task_count": left_out,
        "dev": dev_ids,
        "test": test_ids,
    }
    SPLIT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SPLIT_FILE, "w", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(spec, indent=2) + "\n")

    chosen = {task.example_id: task for task in pool}
    environments = len({chosen[i].env_key for i in dev_ids + test_ids})
    print(f"\nChosen libraries: {', '.join(sorted(libraries))}")
    if skipped:
        print(f"Skipped versions: {', '.join(sorted(skipped))} ({left_out} tasks left out: {args.skip_reason})")
    print(f"dev: {len(dev_ids)} tasks   test: {len(test_ids)} tasks   environments to build: {environments}")
    print(f"Wrote {SPLIT_FILE}. Commit it before running any model on the test split.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
