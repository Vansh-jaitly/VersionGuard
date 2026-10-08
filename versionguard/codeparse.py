"""Turn a model's answer into a runnable program.

A benchmark task gives `starting_code` that ends in an unfinished function
(or class) definition, and a `test` that calls it. Models answer in different
shapes: the whole file, just the function, or only the body. This module
accepts all three and builds: candidate code, then the test.

`extract_python_code` is ported from OmniLearn's eval/evaluate.py.
"""

from __future__ import annotations

import ast
import re
import textwrap
from dataclasses import dataclass
from typing import Optional

PYTHON_FENCE_RE = re.compile(r"```(?:python|py)[^\n]*\n(.*?)```", flags=re.IGNORECASE | re.DOTALL)
ANY_FENCE_RE = re.compile(r"```[^\n]*\n(.*?)```", flags=re.DOTALL)
OPEN_FENCE_RE = re.compile(r"```(?:python|py)?[^\n]*\n(.*)$", flags=re.IGNORECASE | re.DOTALL)
TOP_LEVEL_DEF_RE = re.compile(r"^(?:async[ \t]+)?(?:def|class)[ \t]+([A-Za-z_]\w*)", flags=re.MULTILINE)


class NoCodeError(ValueError):
    """The answer contained nothing that parses as Python for this task."""


@dataclass(frozen=True)
class Program:
    source: str  # candidate code followed by the test
    candidate: str  # candidate code only
    candidate_lines: int  # lines 1..candidate_lines belong to the candidate
    mode: str  # "full", "function" or "body"


def _parses(code: str) -> bool:
    try:
        ast.parse(code)
    except (SyntaxError, ValueError):
        return False
    return True


def code_candidates(answer: str) -> list[str]:
    """Code blocks found in an answer, most trustworthy first."""
    found: list[str] = []
    found.extend(PYTHON_FENCE_RE.findall(answer))
    found.extend(ANY_FENCE_RE.findall(answer))
    if not found:
        # A fence the model opened but never closed (answer cut off).
        open_fence = OPEN_FENCE_RE.search(answer)
        if open_fence:
            found.append(open_fence.group(1))
    found.append(answer)
    seen: set[str] = set()
    unique: list[str] = []
    for item in found:
        if item.strip() and item not in seen:
            seen.add(item)
            unique.append(item)
    return unique


def extract_python_code(answer: str) -> str:
    """First block in the answer that parses and defines a function or class."""
    for candidate in code_candidates(answer):
        candidate = candidate.strip("\n")
        try:
            tree = ast.parse(textwrap.dedent(candidate))
        except (SyntaxError, ValueError):
            continue
        if any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) for n in tree.body):
            return textwrap.dedent(candidate)
    raise NoCodeError("No parseable Python function or class found in the answer")


def target_name(starting_code: str) -> Optional[str]:
    """Name of the last top-level def/class in the starting code (the one to finish)."""
    matches = TOP_LEVEL_DEF_RE.findall(starting_code)
    return matches[-1] if matches else None


def preamble(starting_code: str) -> str:
    """Everything in the starting code before the definition to finish (imports, helpers)."""
    matches = list(TOP_LEVEL_DEF_RE.finditer(starting_code))
    if not matches:
        return starting_code
    return starting_code[: matches[-1].start()]


def _defines(code: str, name: str) -> bool:
    try:
        tree = ast.parse(code)
    except (SyntaxError, ValueError):
        return False
    return any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == name
        for node in tree.body
    )


def complete_with_body(starting_code: str, body: str) -> str:
    """starting_code + an indented body (how the reference solutions are stored)."""
    head = starting_code.rstrip(" \t")
    if not head.endswith("\n"):
        head += "\n"
    block = textwrap.indent(textwrap.dedent(body.strip("\n")), "    ")
    return head + block + "\n"


def reference_program(starting_code: str, solution: str, test: str) -> Program:
    """The benchmark's own solution, assembled the way the benchmark stores it."""
    candidate = starting_code + solution
    if not _parses(candidate):
        candidate = complete_with_body(starting_code, solution)
    return _with_test(candidate, test, "reference")


def _with_test(candidate: str, test: str, mode: str) -> Program:
    candidate = candidate.rstrip() + "\n"
    source = candidate + "\n" + test.strip("\n") + "\n"
    return Program(
        source=source,
        candidate=candidate,
        candidate_lines=candidate.count("\n"),
        mode=mode,
    )


def assemble_program(starting_code: str, answer: str, test: str) -> Program:
    """Build candidate + test from a raw model answer. Raises NoCodeError."""
    name = target_name(starting_code)
    head = preamble(starting_code)

    # 1 and 2: the answer contains the finished definition (whole file or just it).
    if name:
        for raw in code_candidates(answer):
            # As written first; dedented only if needed (dedent also rewrites
            # blank lines inside docstrings).
            for block in (raw.strip("\n"), textwrap.dedent(raw.strip("\n"))):
                if not _defines(block, name):
                    continue
                mode = "full" if head.strip() and head.strip() in block else "function"
                candidate = block if mode == "full" else head + block
                if _parses(candidate):
                    return _with_test(candidate, test, mode)

    # 3: the answer is only the rest of the unfinished definition.
    # Starting code ends in one of two ways. Cleanly (a blank line, a comment,
    # or the "def ...:" line itself): the answer is a block that goes on new,
    # indented lines. Or mid-statement ("    return ", "    return np."): the
    # answer continues that very line, and a new line would leave a bare return.
    last_line = starting_code.rsplit("\n", 1)[-1].strip()
    ends_cleanly = not last_line or last_line.startswith("#") or last_line.endswith(":")
    for block in code_candidates(answer):
        if ends_cleanly:
            attempts = [complete_with_body(starting_code, block)]
        else:
            attempts = [starting_code + block.strip("\n"), starting_code + block.strip()]
        for candidate in attempts:
            if _parses(candidate) and (name is None or _defines(candidate, name)):
                return _with_test(candidate, test, "body")

    raise NoCodeError(
        f"The answer does not contain a usable definition of {name!r}"
        if name
        else "The answer does not contain usable Python code"
    )
