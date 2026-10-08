"""Validate a teammate's complete test run before copying it into results/."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

from experiment.dataset import DATA_FILE, RETRIEVAL_CACHE, SPLIT_FILE, sha256_of, tasks_for
from experiment.report import coverage_issues, load_results
from experiment.run import PROTOCOL_FILE, results_path
from versionguard.config import REPO_ROOT


def validate(path: Path, destination: Path) -> tuple[str, Path]:
    metadata_path = path.with_suffix('.meta.json')
    metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
    model = metadata['model']
    if metadata.get('split') != 'test' or model.startswith('fake:') or path.name != results_path('test', model).name:
        raise ValueError('Expected a real-model test JSONL with the standard name and matching metadata.')
    inputs = {'dataset_sha256': DATA_FILE, 'split_sha256': SPLIT_FILE, 'retrieval_cache_sha256': RETRIEVAL_CACHE,
              'protocol_sha256': PROTOCOL_FILE}
    for key, source in inputs.items():
        if metadata.get(key) != sha256_of(source):
            raise ValueError(f'Teammate run does not match current {key}.')
    fixed = {'temperature': 0.0, 'seed': 42, 'num_ctx': 4096, 'num_predict': 768, 'exec_timeout_s': 120}
    for key, value in fixed.items():
        if metadata.get(key) != value:
            raise ValueError(f'Teammate run does not use the registered {key}.')
    if not metadata.get('llm', {}).get('model_digest') or not metadata.get('llm', {}).get('ollama_version'):
        raise ValueError('Model digest and Ollama version are required.')
    with tempfile.TemporaryDirectory() as directory:
        staging = Path(directory)
        if destination.exists():
            for existing in destination.glob('test-*.jsonl'):
                if existing.name != path.name:
                    shutil.copyfile(existing, staging / existing.name)
                    existing_meta = existing.with_suffix('.meta.json')
                    if existing_meta.is_file():
                        shutil.copyfile(existing_meta, staging / existing_meta.name)
        shutil.copyfile(path, staging / path.name)
        shutil.copyfile(metadata_path, staging / metadata_path.name)
        models, metas = load_results('test', staging)
        issues = coverage_issues('test', models, metas)
        if issues:
            raise ValueError(' '.join(issues))
        tasks = {task.example_id: task for task in tasks_for('test')}
        for task_id, cells in models[model].items():
            task = tasks[task_id]
            for cell in cells.values():
                if any(cell.get(key) != getattr(task, key) for key in ('library', 'version', 'python_version')):
                    raise ValueError(f'Task {task_id} has different pinned environment details.')
    for source in (path, metadata_path):
        target = destination / source.name
        if target.exists() and target.read_bytes() != source.read_bytes():
            raise ValueError(f'Refusing to overwrite existing result: {target}')
    return model, metadata_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('jsonl', type=Path)
    parser.add_argument('--results-dir', type=Path, default=REPO_ROOT / 'results')
    parser.add_argument('--apply', action='store_true', help='copy the validated JSONL and metadata into results/')
    args = parser.parse_args(argv)
    try:
        model, meta = validate(args.jsonl, args.results_dir)
        if args.apply:
            args.results_dir.mkdir(parents=True, exist_ok=True)
            for source in (args.jsonl, meta):
                target = args.results_dir / source.name
                if target.exists():
                    continue
                temporary = target.with_suffix(target.suffix + '.tmp')
                shutil.copyfile(source, temporary)
                temporary.replace(target)
        print(f'Validated {model}: 40 tasks and all 240 condition cells; {"imported" if args.apply else "preview only"}.')
        print('Next: python -m experiment.report --split test --require-complete')
        return 0
    except (OSError, ValueError, KeyError) as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
