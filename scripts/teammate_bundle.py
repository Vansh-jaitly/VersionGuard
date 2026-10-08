"""Build or verify a curated teammate ZIP with a per-file SHA-256 manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path, PurePosixPath

from experiment.report import coverage_issues, load_results
from versionguard.config import REPO_ROOT

TREES = ('versionguard', 'experiment', 'tests', 'scripts', 'docs', 'demo', '.github')
ROOT_FILES = ('README.md', 'pyproject.toml', '.gitignore', '.gitattributes', 'requirements.txt',
              'requirements-dev.txt', 'requirements-lookup.txt', 'requirements-ci.txt', 'data/gitchameleon.jsonl')
RESULT_FILES = ('report-dev.md', 'report-test.md', 'summary-dev.csv', 'summary-test.csv',
                'comparisons-dev.csv', 'comparisons-test.csv', 'failures-dev.csv', 'failures-test.csv',
                'dev-qwen2.5_7b-instruct.jsonl', 'dev-qwen2.5_7b-instruct.meta.json',
                'test-qwen2.5_7b-instruct.jsonl', 'test-qwen2.5_7b-instruct.meta.json',
                'coverage-baseline.json', 'repair-demo-initial.json', 'repair-demo.json',
                'repair-demo-verification.json', 'guard-demo.json', 'coverage-integration.json', 'integration-validation.md')


def selected_files(root: Path) -> list[Path]:
    files = [root / filename for filename in ROOT_FILES]
    files += [root / 'results' / filename for filename in RESULT_FILES]
    for tree in TREES:
        files += [path for path in (root / tree).rglob('*') if path.is_file()
                  and not any(part in {'__pycache__', '.pytest_cache', '.ruff_cache'} for part in path.parts)
                  and path.suffix != '.pyc']
    for path in files:
        if not path.is_file():
            raise ValueError(f'Missing handoff file: {path}')
        if path.resolve() != root.resolve() / path.relative_to(root):
            raise ValueError(f'Symlinks are not included in the handoff: {path}')
    return sorted(set(files))


def write_bundle(root: Path, files: list[Path], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix('.zip.tmp')
    manifest = {'format': 1, 'model': 'qwen2.5:7b-instruct', 'files': {}}
    try:
        with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for path in files:
                relative = path.relative_to(root).as_posix()
                name = 'VersionGuard/' + relative
                data = path.read_bytes()
                archive.writestr(name, data)
                manifest['files'][name] = {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}
            archive.writestr('VersionGuard/HANDOFF_MANIFEST.json', json.dumps(manifest, indent=2) + '\n')
        verify_bundle(temporary)
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)


def verify_bundle(path: Path) -> int:
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(set(names)) != len(names):
            raise ValueError('Bundle has duplicate paths.')
        for name in names:
            parts = PurePosixPath(name)
            if parts.is_absolute() or '..' in parts.parts or '\\' in name or ':' in name or parts.parts[0] != 'VersionGuard':
                raise ValueError('Bundle has an invalid path.')
        manifest = json.loads(archive.read('VersionGuard/HANDOFF_MANIFEST.json'))
        if manifest.get('format') != 1:
            raise ValueError('Unsupported manifest format.')
        files = manifest['files']
        if set(names) != set(files) | {'VersionGuard/HANDOFF_MANIFEST.json'}:
            raise ValueError('Bundle file list differs from its manifest.')
        for name, expected in files.items():
            data = archive.read(name)
            if len(data) != expected['bytes'] or hashlib.sha256(data).hexdigest() != expected['sha256']:
                raise ValueError(f'Bundle checksum mismatch: {name}')
        return len(files)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=REPO_ROOT / 'deliverables' / 'VersionGuard-teammate.zip')
    parser.add_argument('--verify', type=Path, help='verify a ZIP instead of building one')
    args = parser.parse_args(argv)
    try:
        if args.verify:
            print(f'Verified {verify_bundle(args.verify)} files in {args.verify}')
            return 0
        for split in ('dev', 'test'):
            models, metas = load_results(split, REPO_ROOT / 'results', 'qwen2.5:7b-instruct')
            issues = coverage_issues(split, models, metas)
            if issues:
                raise ValueError('Incomplete evaluation: ' + ' '.join(issues))
        write_bundle(REPO_ROOT, selected_files(REPO_ROOT), args.output)
        print(f'Created {args.output}; {verify_bundle(args.output)} files verified')
        return 0
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
