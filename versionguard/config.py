"""Settings, read once from environment variables.

Every value that can change an answer (model, temperature, seed, context
window, number of retrieved documents, documentation budget) lives here so
that a run can record them and a second laptop can reproduce them.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


def _float(name: str, default: float) -> float:
    return float(os.getenv(name, str(default)))


@dataclass(frozen=True)
class Settings:
    # Ollama
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "qwen2.5:7b-instruct")
    # Ollama's own default context is small and truncates silently, so it is
    # always passed explicitly.
    num_ctx: int = _int("OLLAMA_NUM_CTX", 4096)
    num_predict: int = _int("OLLAMA_NUM_PREDICT", 768)
    temperature: float = _float("VG_TEMPERATURE", 0.0)
    seed: int = _int("VG_SEED", 42)

    # Retrieval
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    retriever_kind: str = os.getenv("VG_RETRIEVER", "vector")  # "vector" or "bm25"
    retriever_k: int = _int("VG_RETRIEVER_K", 3)
    # Same documentation budget (characters) in every condition that shows docs.
    doc_char_budget: int = _int("VG_DOC_CHAR_BUDGET", 2400)

    # Execution
    exec_timeout_s: int = _int("VG_EXEC_TIMEOUT_S", 120)

    def as_dict(self) -> dict:
        return asdict(self)


settings = Settings()

DATA_DIR = REPO_ROOT / "data"
APIDOCS_DIR = DATA_DIR / "apidocs"
CHROMA_DIR = DATA_DIR / "chroma"
RESULTS_DIR = REPO_ROOT / "results"
