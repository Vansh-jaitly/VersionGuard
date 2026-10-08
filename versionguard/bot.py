"""The bot: look documentation up for the pinned version, then ask the model."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional, Sequence

from versionguard import apidocs
from versionguard.check import check_source
from versionguard.codeparse import code_candidates
from versionguard.config import APIDOCS_DIR, settings
from versionguard.llm import LLMResult, make_llm
from versionguard.prompts import build_question_prompt, build_question_repair_prompt
from versionguard.repair import FRAME_RE, MAX_FEEDBACK_CHARS, last_error, sanitize_feedback
from versionguard.store import ApiDoc, format_docs, get_retriever, load_api_docs


@dataclass
class BotAnswer:
    text: str
    library: str
    version: str
    sources: list[ApiDoc] = field(default_factory=list)
    result: Optional[LLMResult] = None
    guard: dict = field(default_factory=lambda: {"status": "not_checked", "findings": []})

    def as_dict(self) -> dict:
        return {
            "answer": self.text,
            "library": self.library,
            "version": self.version,
            "sources": [doc.qualname for doc in self.sources],
            "metrics": self.result.metrics if self.result else {},
            "latency_ms": self.result.latency_ms if self.result else None,
            "guard": self.guard,
        }


def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", text).strip("-")


def docs_for_installed(library: str, cache_dir: Optional[Path] = None) -> tuple[list[ApiDoc], str]:
    """Documentation entries for a library installed in THIS environment.

    Returns (entries, version). The extraction is cached per version.
    """
    version = apidocs.dist_version(library) or "unknown"
    cache_dir = Path(cache_dir or APIDOCS_DIR)
    cache = cache_dir / f"local-{_slug(library)}-{_slug(version)}.jsonl"
    if not cache.is_file():
        entries: list[dict] = []
        for module in apidocs.top_level_modules(library):
            entries.extend(apidocs.walk(module, library, version))
        if not entries:
            raise RuntimeError(f"Could not read any documentation from installed library '{library}'")
        cache_dir.mkdir(parents=True, exist_ok=True)
        with open(cache, "w", encoding="utf-8") as stream:
            for entry in entries:
                stream.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return load_api_docs(cache), version


class Bot:
    def __init__(self, model: Optional[str] = None, retriever_kind: Optional[str] = None, k: Optional[int] = None):
        self.llm = make_llm(model)
        self.retriever_kind = retriever_kind or settings.retriever_kind
        self.k = k or settings.retriever_k

    def lookup(self, question: str, docs: Sequence[ApiDoc], name: str) -> list[ApiDoc]:
        retriever = get_retriever(docs, name, self.retriever_kind)
        return [doc for doc, _score in retriever.search(question, self.k)]

    def ask(
        self,
        question: str,
        library: str,
        version: Optional[str] = None,
        docs: Optional[Sequence[ApiDoc]] = None,
        use_docs: bool = True,
        code: Optional[str] = None,
        error_log: Optional[str] = None,
        program_name: str = "prog.py",
    ) -> BotAnswer:
        if (code is None) != (error_log is None):
            raise ValueError("Repair needs both source code and an error log.")
        if docs is None:
            docs, installed = docs_for_installed(library)
            if version and version != installed:
                raise RuntimeError(
                    f"{library} {installed} is installed here, not {version}. "
                    f"Pass --docs with the entries extracted for {version}."
                )
            version = installed
        else:
            known_versions = {doc.version for doc in docs if doc.library == library and doc.version}
            if len(known_versions) > 1:
                raise RuntimeError(f"Documentation mixes multiple versions of {library}; use one pinned version.")
            documented = next(iter(known_versions), None)
            if version and documented and version != documented:
                raise RuntimeError(f"Documentation is for {library} {documented}, not {version}.")
            version = version or documented
        version = version or "unknown"
        query = question
        feedback = ""
        if code is not None:
            log = error_log or ""
            if last_error(log)[0] or any(FRAME_RE.match(line) for line in log.splitlines()):
                feedback = sanitize_feedback(log, len(code.splitlines()), program_name)
            else:
                # Build and guard logs are not tracebacks; preserve their diagnostics.
                feedback = log.strip()[-MAX_FEEDBACK_CHARS:] or "The build failed without a diagnostic."
            query += f"\n{code}"
        sources = self.lookup(query, docs, f"{library}-{version}") if use_docs else []
        if code is None:
            system, user = build_question_prompt(question, library, version, format_docs(sources))
        else:
            system, user = build_question_repair_prompt(question, library, version, format_docs(sources), code, feedback)
        result = self.llm.generate(system, user)
        guard: dict = {"status": "not_checked", "findings": []}
        installed = apidocs.dist_version(library)
        if installed and installed == version:
            candidates = code_candidates(result.text)
            if candidates:
                findings = check_source(candidates[0], "<model>", [Path.cwd()])
                errors = any(finding.level == "error" for finding in findings)
                guard = {"status": "failed" if errors else "clean", "findings": [asdict(finding) for finding in findings]}
            else:
                guard["reason"] = "No Python code was returned."
        else:
            guard["reason"] = f"Static checking requires {library} {version} installed here; found {installed or 'not installed'}."
        return BotAnswer(result.text, library, version, sources, result, guard)
