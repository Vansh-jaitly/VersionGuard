"""Download the GitChameleon 2.0 problems into data/gitchameleon.jsonl.

    python -m experiment.fetch_data                      # from the public dataset API
    python -m experiment.fetch_data --from-repo ../GitChameleonBenchmark

Source: https://github.com/mrcabbage972/GitChameleonBenchmark
Dataset: https://huggingface.co/datasets/cabbage972/GitChameleon-2.0
Paper:   https://arxiv.org/abs/2507.12367
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Optional

from experiment.dataset import DATA_FILE, sha256_of, write_jsonl

API = "https://datasets-server.huggingface.co/rows"
DATASET = "cabbage972/GitChameleon-2.0"
REQUIRED = {"example_id", "library", "version", "problem", "starting_code", "test"}


def fetch_from_api(config: str = "problems", split: str = "train", page: int = 100) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    total: Optional[int] = None
    while total is None or offset < total:
        query = urllib.parse.urlencode(
            {"dataset": DATASET, "config": config, "split": split, "offset": offset, "length": page}
        )
        request = urllib.request.Request(f"{API}?{query}", headers={"User-Agent": "versionguard"})
        for attempt in range(4):
            try:
                with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310 - fixed https URL
                    payload = json.loads(response.read().decode("utf-8"))
                break
            except Exception as exc:  # noqa: BLE001 - retry any transient failure
                if attempt == 3:
                    raise RuntimeError(f"Could not download rows at offset {offset}: {exc}") from exc
                time.sleep(2 * (attempt + 1))
        batch = payload.get("rows", [])
        if not batch:
            break
        for item in batch:
            if isinstance(item, dict) and item.get("truncated_cells"):
                raise RuntimeError(
                    "The dataset API returned shortened cells; use --from-repo with a clone of "
                    "GitChameleonBenchmark instead."
                )
            rows.append(item["row"] if isinstance(item, dict) and "row" in item else item)
        total = payload.get("num_rows_total", total)
        offset += len(batch)
        print(f"  downloaded {offset}/{total if total is not None else '?'}", flush=True)
    return rows


def _load_any(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    data = json.loads(text)
    if isinstance(data, dict):
        data = data.get("rows") or data.get("data") or list(data.values())
    return [row for row in data if isinstance(row, dict)]


def fetch_from_repo(repo: Path) -> list[dict]:
    """Merge every task file under <repo>/dataset by example_id."""
    folder = repo / "dataset"
    if not folder.is_dir():
        raise FileNotFoundError(f"{folder} not found; is {repo} a clone of GitChameleonBenchmark?")
    merged: dict[str, dict] = {}
    used: list[str] = []
    for path in sorted(folder.rglob("*.json*")):
        try:
            rows = _load_any(path)
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        rows = [row for row in rows if "example_id" in row]
        if not rows:
            continue
        used.append(str(path.relative_to(repo)))
        visible = "visible" in path.name.lower()
        for row in rows:
            target = merged.setdefault(str(row["example_id"]), {})
            for key, value in row.items():
                if visible and key == "test":
                    key = "visible_test"
                if key not in target or target[key] in (None, "", []):
                    target[key] = value
    print("  read: " + ", ".join(used))
    return list(merged.values())


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("--from-repo", help="path to a local clone of GitChameleonBenchmark")
    parser.add_argument("--out", default=str(DATA_FILE))
    args = parser.parse_args(argv)

    print("Fetching GitChameleon 2.0 problems ...")
    rows = fetch_from_repo(Path(args.from_repo)) if args.from_repo else fetch_from_api()
    usable = [row for row in rows if REQUIRED <= set(row) and row.get("test")]
    if not usable:
        print("error: no usable task rows found", file=sys.stderr)
        return 1
    usable.sort(key=lambda row: (len(str(row["example_id"])), str(row["example_id"])))
    out = Path(args.out)
    write_jsonl(out, usable)

    libraries = Counter(str(row["library"]) for row in usable)
    print(f"\nWrote {len(usable)} tasks to {out}")
    print(f"sha256: {sha256_of(out)}")
    print(f"{len(libraries)} libraries: " + ", ".join(f"{name} ({n})" for name, n in libraries.most_common()))
    if len(usable) != 328:
        print(f"note: the paper reports 328 tasks; this file has {len(usable)}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
