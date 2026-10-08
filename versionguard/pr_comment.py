"""Render a proposed repair as a PR comment without claiming test validation."""

from __future__ import annotations

import html
import re

MARKER = '<!-- versionguard-repair -->'


def fence(text: str, language: str = '') -> str:
    longest = max((len(match) for match in re.findall(r'`+', text)), default=0)
    delimiter = '`' * max(3, longest + 1)
    return f'{delimiter}{language}\n{text.rstrip()}\n{delimiter}'


def render(answer: dict, source: str, head_sha: str, model: str) -> str:
    guard = answer.get('guard', {})
    status = guard.get('status', 'not_checked')
    context = html.escape(f"{source} | {answer['library']} {answer['version']} | {model}")
    lines = [MARKER, '## VersionGuard repair proposal', '', context, '',
             f'Reviewed commit: `{head_sha}`', '',
             f'Static guard: **{status}**. The proposal has not been executed or tested.', '']
    if guard.get('reason'):
        lines += [html.escape(str(guard['reason'])), '']
    if guard.get('findings'):
        lines += [fence('\n'.join(f"{f['code']}: {f['message']}" for f in guard['findings']), 'text'), '']
    # Fence the whole answer: model output cannot inject comment headings/mentions.
    lines += [fence(str(answer['answer']), 'text'), '', 'Documentation sources:', '']
    lines += [fence('\n'.join(answer.get('sources', [])) or 'No documentation retrieved.', 'text'), '']
    return '\n'.join(lines)
