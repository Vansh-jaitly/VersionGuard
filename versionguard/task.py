"""A coding task pinned to one library version (the benchmark's unit of work)."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any, Optional


def _clean(value: Any) -> str:
    return "" if value is None else str(value)


@dataclass(frozen=True)
class Task:
    example_id: str
    library: str
    version: str
    python_version: str
    problem: str
    starting_code: str
    test: str
    solution: str = ""
    type_of_change: str = ""
    name_of_class_or_func: str = ""
    additional_dependencies: str = ""
    extra_dependencies: str = ""
    api_calls: tuple[str, ...] = ()
    doc_urls: tuple[str, ...] = ()
    visible_test: str = ""
    # Only present in the hand-written self-check tasks (see experiment/fixtures).
    stale_solution: str = ""
    raw: dict = field(default_factory=dict, compare=False, hash=False, repr=False)

    @classmethod
    def from_row(cls, row: dict) -> "Task":
        docs = row.get("docs") or []
        if isinstance(docs, str):
            docs = [docs]
        return cls(
            example_id=str(row["example_id"]),
            library=_clean(row.get("library")).strip(),
            version=_clean(row.get("version")).strip(),
            python_version=_clean(row.get("python_version")).strip() or "3.10",
            problem=_clean(row.get("problem")).strip(),
            starting_code=_clean(row.get("starting_code")),
            test=_clean(row.get("test")),
            solution=_clean(row.get("solution")),
            type_of_change=_clean(row.get("type_of_change")).strip(),
            name_of_class_or_func=_clean(row.get("name_of_class_or_func")).strip(),
            additional_dependencies=_clean(row.get("additional_dependencies")).strip(),
            extra_dependencies=_clean(row.get("extra_dependencies")).strip(),
            api_calls=tuple(str(c) for c in (row.get("api_calls") or [])),
            doc_urls=tuple(str(d) for d in docs if isinstance(d, str)),
            visible_test=_clean(row.get("visible_test")),
            stale_solution=_clean(row.get("stale_solution")),
            raw=row,
        )

    @property
    def requirements(self) -> tuple[str, ...]:
        """pip requirement strings for this task's environment, main library first."""
        reqs = [f"{self.library}=={self.version}"]
        for blob in (self.additional_dependencies, self.extra_dependencies):
            for item in re.split(r"[\s,]+", blob):
                item = item.strip()
                if item and item.lower() not in {"none", "null", "nan"} and item not in reqs:
                    reqs.append(item)
        return tuple(reqs)

    @property
    def distributions(self) -> tuple[str, ...]:
        """Distribution names whose documentation is relevant (library + its extras)."""
        names: list[str] = []
        for req in self.requirements:
            name = re.split(r"[<>=!~\[ ]", req, maxsplit=1)[0].strip()
            if name and name not in names:
                names.append(name)
        return tuple(names)

    @property
    def env_key(self) -> str:
        """Stable id of the environment; tasks with the same key share one image."""
        blob = "|".join((self.python_version, *sorted(self.requirements)))
        digest = hashlib.sha256(blob.encode()).hexdigest()[:10]
        safe = re.sub(r"[^a-z0-9]+", "-", f"{self.library}-{self.version}".lower()).strip("-")
        return f"py{self.python_version.replace('.', '')}-{safe}-{digest}"

    @property
    def feedback_test(self) -> str:
        """Test used to produce repair feedback (the visible one when it exists)."""
        return self.visible_test or self.test

    def optional(self, name: str) -> Optional[str]:
        value = getattr(self, name, "")
        return value or None
