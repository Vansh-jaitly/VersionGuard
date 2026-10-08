"""Loading tasks and splits.

The benchmark data is GitChameleon 2.0 (Apache-2.0 code, MIT dataset card).
It is downloaded by `python -m experiment.fetch_data` into data/ and is not
committed to this repository.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable, Optional

from versionguard.config import DATA_DIR, REPO_ROOT
from versionguard.task import Task

DATA_FILE = DATA_DIR / "gitchameleon.jsonl"
SPLIT_FILE = REPO_ROOT / "experiment" / "splits" / "split.json"
FIXTURE_DIR = REPO_ROOT / "experiment" / "fixtures"
FIXTURE_TASKS = FIXTURE_DIR / "tasks.jsonl"
FIXTURE_LIBS = FIXTURE_DIR / "libs"
RETRIEVAL_CACHE = REPO_ROOT / "experiment" / "retrieval_cache.json"
FIXTURE_RETRIEVAL_CACHE = FIXTURE_DIR / "retrieval_cache.json"

SPLITS = ("fixtures", "dev", "test", "all")


def sha256_of(path: Path) -> str:
    """Hash of a text file's content, the same on Windows and macOS.

    Line endings are normalised first: git may check a file out with CRLF on
    Windows, and two laptops must report the same hash for the same content.
    """
    data = Path(path).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with open(path, encoding="utf-8") as stream:
        for line in stream:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")


def load_tasks(path: Optional[Path] = None) -> list[Task]:
    path = Path(path or DATA_FILE)
    if not path.is_file():
        raise FileNotFoundError(
            f"{path} not found. Download the benchmark first: python -m experiment.fetch_data"
        )
    return [Task.from_row(row) for row in read_jsonl(path)]


def load_split_file(path: Optional[Path] = None) -> dict:
    path = Path(path or SPLIT_FILE)
    if not path.is_file():
        raise FileNotFoundError(
            f"{path} not found. Choose the tasks first: python -m experiment.select_tasks"
        )
    return json.loads(path.read_text(encoding="utf-8"))


def tasks_for(split: str) -> list[Task]:
    """Tasks of a split, in a fixed order."""
    if split not in SPLITS:
        raise ValueError(f"Unknown split '{split}'. Choose from {', '.join(SPLITS)}")
    if split == "fixtures":
        return load_tasks(FIXTURE_TASKS)
    tasks = {task.example_id: task for task in load_tasks()}
    spec = load_split_file()
    if spec.get("dataset_sha256") != sha256_of(DATA_FILE):
        raise ValueError("Benchmark data differs from the data used to select the split; restore the original dataset.")
    ids = spec["dev"] + spec["test"] if split == "all" else spec[split]
    missing = [i for i in ids if i not in tasks]
    if missing:
        raise KeyError(f"Split refers to tasks missing from the data file: {missing[:5]}")
    return [tasks[i] for i in ids]


def retrieval_cache_path(split: str) -> Path:
    return FIXTURE_RETRIEVAL_CACHE if split == "fixtures" else RETRIEVAL_CACHE
