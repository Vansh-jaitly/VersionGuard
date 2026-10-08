"""Propose a repair from a PR file using local Ollama; posting requires --post."""

from __future__ import annotations

import argparse
import base64
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath
from urllib.parse import quote

from versionguard.config import REPO_ROOT, settings
from versionguard.pr_comment import MARKER, render


def gh_json(endpoint: str, payload: dict | None = None, method: str = 'GET', paginate: bool = False):
    command = ['gh', 'api', endpoint, '--method', method]
    if paginate:
        command += ['--paginate', '--slurp']
    if payload is not None:
        command += ['--input', '-']
    result = subprocess.run(command, input=json.dumps(payload) if payload is not None else None,
                            capture_output=True, text=True, encoding='utf-8', check=False, timeout=120)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or 'GitHub request failed')
    return json.loads(result.stdout)


def head(repo: str, pr: int) -> tuple[str, str]:
    metadata = gh_json(f'repos/{repo}/pulls/{pr}')
    if metadata.get('state') != 'open':
        raise ValueError('The pull request must be open.')
    commit = metadata['head']['sha']
    if not re.fullmatch(r'[0-9a-fA-F]{40}', commit):
        raise ValueError('GitHub returned an invalid head commit.')
    source_repo = (metadata['head'].get('repo') or {}).get('full_name', '')
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', source_repo):
        raise ValueError('The PR source repository is unavailable.')
    return commit, source_repo


def post_comment(repo: str, pr: int, body: str) -> None:
    login = gh_json('user')['login']
    pages = gh_json(f'repos/{repo}/issues/{pr}/comments', paginate=True)
    owned = [comment for page in pages for comment in page
             if comment.get('user', {}).get('login') == login and comment.get('body', '').startswith(MARKER)]
    if owned:
        gh_json(f"repos/{repo}/issues/comments/{owned[-1]['id']}", {'body': body}, 'PATCH')
    else:
        gh_json(f'repos/{repo}/issues/{pr}/comments', {'body': body}, 'POST')


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', required=True, help='GitHub owner/repository')
    parser.add_argument('--pr', required=True, type=int)
    parser.add_argument('--code', required=True, help='repository-relative Python file in the PR')
    parser.add_argument('--error-log', required=True, type=Path, help='local build or guard log')
    parser.add_argument('--library', required=True)
    parser.add_argument('--version')
    parser.add_argument('--docs', type=Path)
    parser.add_argument('--model', default=settings.ollama_model)
    parser.add_argument('--question', default='Repair this program using the pinned library documentation.')
    parser.add_argument('--output', type=Path, default=REPO_ROOT / 'results' / 'pr-repair.md')
    parser.add_argument('--post', action='store_true', help='publish/update your VersionGuard comment after checking the PR head')
    args = parser.parse_args(argv)
    path = PurePosixPath(args.code)
    if (not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', args.repo) or args.pr <= 0
            or path.is_absolute() or '..' in path.parts or '\\' in args.code or ':' in args.code or path.suffix != '.py'):
        parser.error('Use owner/repository, a positive PR number and a repository-relative .py path.')
    try:
        log = args.error_log.resolve(strict=True)
        commit, source_repo = head(args.repo, args.pr)
        data = gh_json(f'repos/{source_repo}/contents/{quote(str(path), safe="/")}?ref={commit}')
        if data.get('type') != 'file' or data.get('encoding') != 'base64' or data.get('size', 0) > 100_000:
            raise ValueError('The PR source must be a regular Python file under 100 KB.')
        source = base64.b64decode(data['content']).decode('utf-8')
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / path.name
            target.write_text(source, encoding='utf-8')
            command = [sys.executable, '-m', 'versionguard.ask', args.question, '--library', args.library,
                       '--model', args.model, '--retriever', 'bm25', '--code', str(target), '--error-log', str(log), '--json']
            if args.version:
                command += ['--version', args.version]
            if args.docs:
                command += ['--docs', str(args.docs.resolve(strict=True))]
            result = subprocess.run(command, cwd=REPO_ROOT, capture_output=True, text=True, encoding='utf-8',
                                    check=False, timeout=600)
        if result.returncode not in (0, 1):
            raise RuntimeError(result.stderr.strip() or 'The bot could not propose a repair.')
        answer = json.loads(result.stdout)
        body = render(answer, str(path), commit, args.model)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(body + '\n', encoding='utf-8')
        args.output.with_suffix('.json').write_text(json.dumps({'repo': args.repo, 'pr': args.pr, 'source': str(path),
                                                              'head_sha': commit, 'model': args.model, 'answer': answer},
                                                             indent=2) + '\n', encoding='utf-8')
        print(f'Repair proposal saved to {args.output}')
        if args.post:
            if head(args.repo, args.pr)[0] != commit:
                raise RuntimeError('The PR changed during generation. Saved proposal was not posted; run again.')
            post_comment(args.repo, args.pr, body)
            print(f'Published repair comment: https://github.com/{args.repo}/pull/{args.pr}')
        return 0
    except (OSError, ValueError, RuntimeError, KeyError, subprocess.TimeoutExpired) as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
