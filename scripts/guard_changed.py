"""Run the guard on changed application files, preserving spaces in filenames."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath


def application_files(output: bytes) -> list[str]:
    paths = []
    for item in output.decode('utf-8').split('\0'):
        path = PurePosixPath(item)
        if (path.suffix == '.py' and path.parts and path.parts[0] in {'versionguard', 'experiment', 'demo', 'scripts'}
                and 'fixtures' not in path.parts and Path(item).is_file()):
            paths.append(item)
    return paths


def main() -> int:
    base, head = os.getenv('VG_BASE_SHA', ''), os.getenv('VG_HEAD_SHA', '')
    if not all(re.fullmatch(r'[0-9a-fA-F]{40}', value) for value in (base, head)):
        print('error: VG_BASE_SHA and VG_HEAD_SHA must be full Git commit hashes', file=sys.stderr)
        return 2
    changed = subprocess.run(['git', 'diff', '--name-only', '-z', '--diff-filter=AM', base, head, '--', '*.py'],
                             capture_output=True, check=True)
    paths = application_files(changed.stdout)
    if not paths:
        print('No changed application Python files to check.')
        return 0
    return subprocess.run([sys.executable, '-m', 'versionguard.check', '--github', *paths], check=False).returncode


if __name__ == '__main__':
    sys.exit(main())
