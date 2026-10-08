"""Read a failed run: classify the failure and prepare feedback for a repair.

Two rules keep the repair round honest:

1. The model never sees the test's source or expected values. Traceback
   frames that belong to the test are dropped, and assertion messages are
   replaced by a generic sentence (assert helpers print the expected values).
2. Failure categories are assigned by this code from the error, not by a
   person or a model, so the failure analysis can be reproduced.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

FRAME_RE = re.compile(r'^\s*File "(?P<file>[^"]+)", line (?P<line>\d+)(?:, in (?P<func>.+))?\s*$')
ERROR_LINE_RE = re.compile(
    r"^(?P<type>[A-Za-z_][\w.]*(?:Error|Exception|Warning|Exit|Interrupt))(?::\s?(?P<msg>.*))?$"
)

API_MISSING_TYPES = {"AttributeError", "ImportError", "ModuleNotFoundError"}
SIGNATURE_HINTS = (
    "unexpected keyword argument",
    "positional argument",
    "required positional",
    "required keyword",
    "takes no arguments",
    "takes exactly",
    "takes at most",
    "takes from",
    "got multiple values",
)
GENERIC_ASSERTION = "AssertionError: the function ran but returned a wrong result for the test input."
MAX_FEEDBACK_CHARS = 1200
MAX_LIBRARY_FRAMES = 2


@dataclass(frozen=True)
class Outcome:
    status: str  # pass | fail | error | timeout | no_code | env_error
    error_type: str = ""  # e.g. AttributeError
    category: str = ""  # api_missing | api_signature | wrong_result | other_error | timeout | no_code
    message: str = ""

    @property
    def passed(self) -> bool:
        return self.status == "pass"


def last_error(stderr: str) -> tuple[str, str]:
    """(exception type, message) from the final traceback line, if any."""
    for line in reversed(stderr.strip().splitlines()):
        match = ERROR_LINE_RE.match(line.strip())
        if match:
            name = match.group("type").rsplit(".", 1)[-1]
            return name, (match.group("msg") or "").strip()
    return "", ""


def classify(returncode: int, stderr: str, timed_out: bool = False) -> Outcome:
    if timed_out:
        return Outcome("timeout", "Timeout", "timeout", "execution exceeded the time limit")
    if returncode == 0:
        return Outcome("pass")
    error_type, message = last_error(stderr)
    if error_type == "AssertionError":
        return Outcome("fail", error_type, "wrong_result", "")
    if error_type in API_MISSING_TYPES:
        return Outcome("error", error_type, "api_missing", message[:300])
    if error_type == "TypeError" and any(hint in message for hint in SIGNATURE_HINTS):
        return Outcome("error", error_type, "api_signature", message[:300])
    return Outcome("error", error_type or "UnknownError", "other_error", message[:300])


def _split_traceback(stderr: str, candidate_lines: int, program_name: str):
    """(frames, tail). A frame is (in_program, is_test_frame, lines)."""
    lines = stderr.strip().splitlines()
    frames: list[tuple[bool, bool, list[str]]] = []
    tail: list[str] = []
    index = 0
    while index < len(lines):
        match = FRAME_RE.match(lines[index])
        if not match:
            if frames:
                tail.append(lines[index])
            index += 1
            continue
        in_program = match.group("file").replace("\\", "/").endswith(program_name)
        is_test = in_program and int(match.group("line")) > candidate_lines
        head = lines[index]
        if in_program:
            head = f'  File "{program_name}"' + head.split('"', 2)[2]
        block = [head]
        index += 1
        # A frame is followed by its source line and, on newer Pythons, markers.
        while index < len(lines) and not FRAME_RE.match(lines[index]) and lines[index].startswith("    "):
            block.append(lines[index])
            index += 1
        frames.append((in_program, is_test, block))
        tail = []  # the tail is whatever follows the LAST frame
    return frames, tail


def sanitize_feedback(stderr: str, candidate_lines: int, program_name: str = "prog.py") -> str:
    """Error log that is safe to show the model for a repair attempt.

    Lines 1..candidate_lines of the program are the candidate's code; anything
    after that is the test and is never shown.
    """
    if not stderr.strip():
        return "The program exited with an error but printed no traceback."
    frames, tail = _split_traceback(stderr, candidate_lines, program_name)
    candidate_frames = [block for in_program, is_test, block in frames if in_program and not is_test]
    library_frames = [block for in_program, _is_test, block in frames if not in_program]

    error_type, _message = last_error(stderr)
    shown: list[str] = []
    if error_type == "AssertionError":
        # Only the candidate's own frames; the message may contain expected values.
        for block in candidate_frames:
            shown.extend(block)
        shown.append(GENERIC_ASSERTION)
    else:
        for block in candidate_frames:
            shown.extend(block)
        for block in library_frames[-MAX_LIBRARY_FRAMES:]:
            shown.extend(block)
        shown.extend(tail if tail else [stderr.strip().splitlines()[-1]])
    if len(shown) > 1 or FRAME_RE.match(shown[0]):
        shown.insert(0, "Traceback (most recent call last):")
    text = "\n".join(shown)
    if len(text) > MAX_FEEDBACK_CHARS:
        text = "...\n" + text[-MAX_FEEDBACK_CHARS:]
    return text.strip()
