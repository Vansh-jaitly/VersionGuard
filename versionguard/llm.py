"""LLM service: one place that talks to Ollama.

Ported from OmniLearn's backend/services/llm_service.py. Changes made for the
experiment: temperature 0 and a fixed seed (was 0.2, unseeded), a cap on the
answer length, synchronous calls, and a scripted stand-in model so the whole
pipeline can be tested without Ollama.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Optional

from versionguard.config import settings


@dataclass
class LLMResult:
    text: str
    metrics: dict[str, Any] = field(default_factory=dict)
    latency_ms: float = 0.0


def extract_metrics(metadata: Any) -> dict[str, Any]:
    """Token counts and Ollama timings (nanoseconds converted to ms)."""
    if not isinstance(metadata, dict):
        metadata = {}

    def token_count(key: str) -> Optional[int]:
        value = metadata.get(key)
        return value if isinstance(value, int) and not isinstance(value, bool) else None

    def duration_ms(key: str) -> Optional[float]:
        value = metadata.get(key)
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return None
        return value / 1_000_000

    return {
        "input_tokens": token_count("prompt_eval_count"),
        "output_tokens": token_count("eval_count"),
        "total_duration_ms": duration_ms("total_duration"),
        "eval_duration_ms": duration_ms("eval_duration"),
        "prompt_eval_duration_ms": duration_ms("prompt_eval_duration"),
    }


class OllamaLLM:
    """A local Ollama model reached through LangChain or Ollama's HTTP API.

    LangChain remains the preferred client when it is installed. The direct
    client is intentionally small and uses the same generation options, so a
    model run can still proceed on machines where optional Python packages
    cannot be installed (for example, an offline CI runner).
    """

    def __init__(self, model: Optional[str] = None, base_url: Optional[str] = None):
        self.model = model or settings.ollama_model
        self.base_url = base_url or settings.ollama_base_url
        self._llm = None

    def _client(self):
        if self._llm is None:
            from langchain_ollama import ChatOllama  # imported late: optional in CI

            self._llm = ChatOllama(
                base_url=self.base_url,
                model=self.model,
                temperature=settings.temperature,
                seed=settings.seed,
                num_ctx=settings.num_ctx,
                num_predict=settings.num_predict,
            )
        return self._llm

    def _generate_http(self, system: str, user: str) -> LLMResult:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "options": {
                "temperature": settings.temperature,
                "seed": settings.seed,
                "num_ctx": settings.num_ctx,
                "num_predict": settings.num_predict,
            },
        }
        request = urllib.request.Request(
            f"{self.base_url.rstrip('/')}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        start = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=max(120, settings.exec_timeout_s)) as response:  # noqa: S310
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace").strip()
            try:
                parsed = json.loads(detail)
                if isinstance(parsed, dict):
                    detail = str(parsed.get("error", detail))
            except (TypeError, ValueError):
                pass
            raise RuntimeError(f"Ollama /api/chat failed with HTTP {exc.code}: {detail[:500]}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Ollama /api/chat is unreachable at {self.base_url}: {exc.reason}") from exc
        latency_ms = (time.perf_counter() - start) * 1000
        message = body.get("message", {})
        content = message.get("content", "") if isinstance(message, dict) else ""
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("Ollama returned an empty response")
        return LLMResult(
            text=content,
            metrics=extract_metrics(body),
            latency_ms=round(latency_ms, 1),
        )

    def generate(self, system: str, user: str, **_ignored: Any) -> LLMResult:
        try:
            from langchain_core.messages import HumanMessage, SystemMessage
            start = time.perf_counter()
            response = self._client().invoke(
                [SystemMessage(content=system), HumanMessage(content=user)]
            )
        except ImportError:
            return self._generate_http(system, user)

        latency_ms = (time.perf_counter() - start) * 1000
        text = response.content if isinstance(response.content, str) else str(response.content)
        return LLMResult(
            text=text,
            metrics=extract_metrics(getattr(response, "response_metadata", None)),
            latency_ms=round(latency_ms, 1),
        )

    def describe(self) -> dict[str, Any]:
        """What a results file needs to say about the model that produced it."""
        info = check_connection(self.base_url, self.model)
        return {
            "kind": "ollama",
            "model": self.model,
            "base_url": self.base_url,
            "model_digest": info.get("configured_model_digest"),
            "ollama_version": info.get("ollama_version"),
        }


class FakeLLM:
    """Scripted stand-in used by tests and by the CI self-check. Not a model.

    fake:reference  always returns the task's reference solution.
    fake:stale      returns the task's `stale_solution` (code written for an
                    older library version) unless the prompt contains
                    documentation, in which case it returns the reference.
    """

    def __init__(self, mode: str):
        if mode not in {"reference", "stale"}:
            raise ValueError(f"Unknown fake model mode: {mode}")
        self.mode = mode
        self.model = f"fake:{mode}"

    def generate(self, system: str, user: str, task: Any = None, **_ignored: Any) -> LLMResult:
        from versionguard.prompts import DOCS_HEADER

        if task is None:  # the interactive bot: there is no scripted answer
            shown = "with" if DOCS_HEADER in user else "without"
            return LLMResult(text=f"```python\n# stand-in model: prompt received {shown} documentation\n```")

        use_reference = self.mode == "reference" or DOCS_HEADER in user
        body = task.solution if use_reference else (task.stale_solution or task.solution)
        code = task.starting_code + body
        return LLMResult(
            text=f"```python\n{code}\n```",
            metrics={"input_tokens": len(user.split()), "output_tokens": len(code.split())},
            latency_ms=0.0,
        )

    def describe(self) -> dict[str, Any]:
        return {"kind": "fake", "model": self.model}


def make_llm(model: Optional[str] = None):
    name = model or settings.ollama_model
    if name.startswith("fake:"):
        return FakeLLM(name.split(":", 1)[1])
    return OllamaLLM(name)


def _get_json(url: str, timeout: float) -> Any:
    request = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - local URL
        return json.loads(response.read().decode())


def check_connection(base_url: Optional[str] = None, model: Optional[str] = None) -> dict[str, Any]:
    """Is Ollama reachable, and is the configured model pulled?

    Two attempts with a generous timeout, as in OmniLearn, so a slow first
    connection is not reported as unreachable.
    """
    base = (base_url or settings.ollama_base_url).rstrip("/")
    wanted = model or settings.ollama_model
    last_error: Optional[str] = None
    for _attempt in range(2):
        try:
            tags = _get_json(f"{base}/api/tags", timeout=8)
            models = tags.get("models", [])
            names = [m.get("name") for m in models]
            digest = next(
                (m.get("digest") for m in models if m.get("name") == wanted), None
            )
            try:
                version = _get_json(f"{base}/api/version", timeout=8).get("version")
            except Exception:  # noqa: BLE001 - version is nice to have
                version = None
            return {
                "connected": True,
                "base_url": base,
                "configured_model": wanted,
                "configured_model_digest": digest,
                "available_models": names,
                "is_configured_model_available": any(wanted == n for n in names),
                "ollama_version": version,
            }
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
    return {
        "connected": False,
        "base_url": base,
        "configured_model": wanted,
        "available_models": [],
        "error": last_error,
    }
