"""Documentation store and lookup.

Two interchangeable retrievers over the same entries:

* VectorRetriever: LangChain + ChromaDB + all-MiniLM-L6-v2 embeddings
  (the same stack OmniLearn used). This is the default.
* Bm25Retriever: keyword search, pure Python. Used as the keyword baseline,
  in CI (no model download), and as a fallback.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Sequence

from versionguard.config import CHROMA_DIR, settings


@dataclass(frozen=True)
class ApiDoc:
    qualname: str
    kind: str = "function"
    signature: str = ""
    doc: str = ""
    library: str = ""
    version: Optional[str] = None

    @property
    def text(self) -> str:
        head = f"{self.qualname}{self.signature}"
        return f"{head}\n{self.doc}".strip()

    def as_dict(self) -> dict:
        return {
            "qualname": self.qualname,
            "kind": self.kind,
            "signature": self.signature,
            "doc": self.doc,
            "library": self.library,
            "version": self.version,
        }


def load_api_docs(path: Path | str) -> list[ApiDoc]:
    docs: list[ApiDoc] = []
    with open(path, encoding="utf-8") as stream:
        for line in stream:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            docs.append(
                ApiDoc(
                    qualname=row["qualname"],
                    kind=row.get("kind", "function"),
                    signature=row.get("signature", ""),
                    doc=row.get("doc", ""),
                    library=row.get("library", ""),
                    version=row.get("version"),
                )
            )
    return docs


def corpus_fingerprint(docs: Sequence[ApiDoc]) -> str:
    digest = hashlib.sha256()
    for doc in docs:
        digest.update(doc.qualname.encode())
        digest.update(b"\0")
        digest.update(doc.signature.encode())
        digest.update(b"\n")
    return digest.hexdigest()[:16]


_CAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_SPLIT = re.compile(r"[^A-Za-z0-9]+")


def tokenize(text: str) -> list[str]:
    """Lower-case word pieces; splits snake_case, dotted.names and camelCase."""
    tokens: list[str] = []
    for chunk in _SPLIT.split(text):
        if not chunk:
            continue
        for piece in _CAMEL.split(chunk):
            piece = piece.lower()
            if len(piece) > 1 or piece.isdigit():
                tokens.append(piece)
    return tokens


# How many raw hits are fetched per entry finally shown.
FETCH_FACTOR = 6


def diversify(hits: Sequence[tuple[ApiDoc, float]], k: int) -> list[tuple[ApiDoc, float]]:
    """Keep one entry per function name, preferring the most direct path.

    A library documents the same function in several places (numpy.any,
    numpy.ndarray.any, numpy.matrix.any). Showing three copies wastes the
    documentation budget, so hits are grouped by their final name; each group
    is represented by its shortest path (the public function rather than a
    method on some class) and groups keep the rank of their best hit.
    """
    groups: dict[str, tuple[int, tuple[ApiDoc, float]]] = {}
    order: list[str] = []
    for hit in hits:
        doc = hit[0]
        name = doc.qualname.rsplit(".", 1)[-1]
        depth = doc.qualname.count(".")
        if name not in groups:
            groups[name] = (depth, hit)
            order.append(name)
        elif depth < groups[name][0]:
            groups[name] = (depth, hit)
    return [groups[name][1] for name in order[:k]]


class Bm25Retriever:
    """Okapi BM25 with an inverted index. The name is weighted above the docstring."""

    kind = "bm25"

    def __init__(self, docs: Sequence[ApiDoc], k1: float = 1.5, b: float = 0.75):
        self.docs = list(docs)
        self.k1 = k1
        self.b = b
        self._postings: dict[str, list[tuple[int, int]]] = defaultdict(list)
        self._lengths: list[int] = []
        for index, doc in enumerate(self.docs):
            # Repeating the name is a simple way to weight it.
            tokens = tokenize(doc.qualname) * 3 + tokenize(doc.signature) + tokenize(doc.doc)
            self._lengths.append(len(tokens))
            for term, freq in Counter(tokens).items():
                self._postings[term].append((index, freq))
        self._avg_len = (sum(self._lengths) / len(self._lengths)) if self._lengths else 0.0

    def search(self, query: str, k: int = 3) -> list[tuple[ApiDoc, float]]:
        if not self.docs:
            return []
        scores: dict[int, float] = defaultdict(float)
        total = len(self.docs)
        for term in set(tokenize(query)):
            postings = self._postings.get(term)
            if not postings:
                continue
            idf = math.log(1 + (total - len(postings) + 0.5) / (len(postings) + 0.5))
            for index, freq in postings:
                norm = freq + self.k1 * (1 - self.b + self.b * self._lengths[index] / self._avg_len)
                scores[index] += idf * freq * (self.k1 + 1) / norm
        # Ties are broken by name so the result never depends on dict order.
        ranked = sorted(scores.items(), key=lambda item: (-item[1], self.docs[item[0]].qualname))
        raw = [(self.docs[index], round(score, 4)) for index, score in ranked[: k * FETCH_FACTOR]]
        return diversify(raw, k)


class VectorRetriever:
    """Embedding search: LangChain's Chroma wrapper with a local embedding model."""

    kind = "vector"

    def __init__(
        self,
        docs: Sequence[ApiDoc],
        name: str,
        persist_dir: Optional[Path] = None,
        embedding_model: Optional[str] = None,
    ):
        from langchain_chroma import Chroma
        from langchain_huggingface import HuggingFaceEmbeddings

        self.docs = list(docs)
        self._by_name = {doc.qualname: doc for doc in self.docs}
        model = embedding_model or settings.embedding_model
        # The collection name includes the corpus fingerprint, so a changed
        # corpus can never be served from a stale index.
        safe = re.sub(r"[^A-Za-z0-9_-]", "_", name)[:40].strip("_-") or "docs"
        collection = f"vg_{safe}_{corpus_fingerprint(self.docs)}"
        directory = Path(persist_dir or CHROMA_DIR)
        directory.mkdir(parents=True, exist_ok=True)
        self._store = Chroma(
            collection_name=collection,
            embedding_function=HuggingFaceEmbeddings(model_name=model),
            persist_directory=str(directory),
        )
        existing = self._store._collection.count()  # noqa: SLF001 - no public count()
        if existing != len(self.docs):
            if existing:
                self._store.delete_collection()
                self._store = Chroma(
                    collection_name=collection,
                    embedding_function=HuggingFaceEmbeddings(model_name=model),
                    persist_directory=str(directory),
                )
            for start in range(0, len(self.docs), 1000):
                batch = self.docs[start : start + 1000]
                self._store.add_texts(
                    texts=[doc.text for doc in batch],
                    metadatas=[{"qualname": doc.qualname} for doc in batch],
                    ids=[f"{start + offset}" for offset in range(len(batch))],
                )

    def search(self, query: str, k: int = 3) -> list[tuple[ApiDoc, float]]:
        hits = self._store.similarity_search_with_score(query, k=k * FETCH_FACTOR)
        out: list[tuple[ApiDoc, float]] = []
        for document, distance in hits:
            doc = self._by_name.get(document.metadata.get("qualname", ""))
            if doc is not None:
                out.append((doc, round(float(distance), 4)))
        return diversify(out, k)


def get_retriever(docs: Sequence[ApiDoc], name: str, kind: Optional[str] = None):
    kind = kind or settings.retriever_kind
    if kind == "bm25":
        return Bm25Retriever(docs)
    if kind == "vector":
        return VectorRetriever(docs, name)
    raise ValueError(f"Unknown retriever kind: {kind}")


def format_docs(docs: Iterable[ApiDoc], budget: Optional[int] = None) -> str:
    """Render entries for a prompt, never exceeding the character budget.

    The budget is shared equally, so one long docstring cannot crowd out the
    others, and every condition that shows documentation gets the same room.
    """
    docs = list(docs)
    if not docs:
        return ""
    budget = budget or settings.doc_char_budget
    share = max(120, budget // len(docs))
    parts = []
    for doc in docs:
        text = doc.text
        if len(text) > share:
            text = text[: share - 4].rstrip() + " ..."
        parts.append(text)
    return "\n\n".join(parts)[:budget]
