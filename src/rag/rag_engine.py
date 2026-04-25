"""
src/rag/rag_engine.py -- Simple local RAG engine for PetChat-2.0 v2.

Features:
- Loads .txt files from the project-level cleaned_txt/ folder
- Chunks documents
- Uses Ollama nomic-embed-text embeddings
- Uses FAISS for vector search when available
- Degrades gracefully if faiss, numpy, or Ollama are unavailable

Public API
----------
_get_engine() -> RagEngine
build_rag_context(query, max_chunks=5, min_score=0.25) -> str
rebuild_index() -> bool
"""

from __future__ import annotations

import hashlib
import json
import logging
import pickle
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _get_config():
    """
    Lazy import to avoid circular imports.
    Expects config.py to point RAG_DOCS_DIR at the project root cleaned_txt/.
    """
    from src.config import (
        OLLAMA_BASE_URL,
        RAG_CACHE_DIR,
        RAG_DOCS_DIR,
        RAG_EMBED_MODEL,
        RAG_ENABLED,
    )

    return OLLAMA_BASE_URL, RAG_DOCS_DIR, RAG_CACHE_DIR, RAG_EMBED_MODEL, RAG_ENABLED


def _deps_available() -> bool:
    try:
        import faiss  # noqa: F401
        import numpy  # noqa: F401
        return True
    except ImportError:
        return False


class _OllamaEmbedder:
    """
    Calls Ollama's embeddings endpoint using stdlib HTTP only.
    """

    def __init__(self, base_url: str, model: str = "nomic-embed-text") -> None:
        self.base_url = (base_url or "").rstrip("/")
        self.model = model

    def _embed_one(self, text: str) -> list[float]:
        if not self.base_url:
            raise RuntimeError("OLLAMA_BASE_URL is not configured.")

        url = f"{self.base_url}/api/embeddings"
        payload = json.dumps(
            {
                "model": self.model,
                "prompt": text,
            }
        ).encode("utf-8")

        request = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Ollama embeddings HTTP {exc.code}: {detail}") from exc
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"Ollama embeddings request failed: {exc}") from exc

        embedding = data.get("embedding")
        if not isinstance(embedding, list) or not embedding:
            raise RuntimeError("Ollama embeddings response did not contain a valid embedding.")

        return [float(x) for x in embedding]

    def encode(
        self,
        texts: list[str],
        normalize_embeddings: bool = True,
        **_: Any,
    ):
        import numpy as np  # noqa: PLC0415

        vectors = [self._embed_one(text) for text in texts]
        arr = np.array(vectors, dtype="float32")

        if normalize_embeddings and arr.size:
            norms = np.linalg.norm(arr, axis=1, keepdims=True)
            arr = arr / np.where(norms == 0, 1.0, norms)

        return arr


def _load_docs(docs_dir: Path) -> list[dict[str, str]]:
    docs: list[dict[str, str]] = []

    if not docs_dir.exists():
        logger.warning("RAG docs dir not found: %s", docs_dir)
        return docs

    for path in sorted(docs_dir.glob("*.txt")):
        try:
            text = path.read_text(encoding="utf-8", errors="replace").strip()
            if text:
                docs.append(
                    {
                        "source": path.name,
                        "text": text,
                    }
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not read %s: %s", path, exc)

    logger.info("Loaded %d RAG documents from %s", len(docs), docs_dir)
    return docs


def _chunk_text(
    text: str,
    source: str,
    chunk_size: int = 400,
    overlap: int = 80,
) -> list[dict[str, str]]:
    words = text.split()
    chunks: list[dict[str, str]] = []

    if not words:
        return chunks

    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk_text = " ".join(words[start:end]).strip()

        if chunk_text:
            chunks.append(
                {
                    "source": source,
                    "text": chunk_text,
                }
            )

        if end >= len(words):
            break

        start += max(1, chunk_size - overlap)

    return chunks


def _build_chunks(docs: list[dict[str, str]]) -> list[dict[str, str]]:
    all_chunks: list[dict[str, str]] = []
    for doc in docs:
        all_chunks.extend(_chunk_text(doc["text"], doc["source"]))
    return all_chunks


def _doc_fingerprint(docs_dir: Path) -> str:
    digest = hashlib.md5()

    for path in sorted(docs_dir.glob("*.txt")):
        try:
            stat = path.stat()
            digest.update(path.name.encode("utf-8"))
            digest.update(str(stat.st_mtime_ns).encode("utf-8"))
            digest.update(str(stat.st_size).encode("utf-8"))
        except Exception:
            continue

    return digest.hexdigest()


class RagEngine:
    """
    Lazy-built singleton-style RAG engine.
    """

    def __init__(self) -> None:
        self._ready = False
        self._chunks: list[dict[str, Any]] = []
        self._index: Any = None
        self._embedder: _OllamaEmbedder | None = None
        self._build()

    def _build(self) -> None:
        if not _deps_available():
            logger.warning("RAG disabled because faiss or numpy is not installed.")
            return

        ollama_base_url, docs_dir, cache_dir, embed_model, rag_enabled = _get_config()

        if not rag_enabled:
            logger.info("RAG is disabled by config.")
            return

        docs_dir = Path(docs_dir)
        cache_dir = Path(cache_dir)

        cache_chunks = cache_dir / "chunks.pkl"
        cache_index = cache_dir / "index.faiss"
        cache_meta = cache_dir / "meta.json"

        fingerprint = _doc_fingerprint(docs_dir)

        if cache_chunks.exists() and cache_index.exists() and cache_meta.exists():
            try:
                import faiss  # noqa: PLC0415

                meta = json.loads(cache_meta.read_text(encoding="utf-8"))
                if (
                    meta.get("fingerprint") == fingerprint
                    and meta.get("model") == embed_model
                ):
                    self._chunks = pickle.loads(cache_chunks.read_bytes())
                    self._index = faiss.read_index(str(cache_index))
                    self._embedder = _OllamaEmbedder(
                        base_url=ollama_base_url,
                        model=embed_model,
                    )
                    self._ready = True
                    logger.info("Loaded cached RAG index with %d chunks.", len(self._chunks))
                    return
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed loading cached RAG index, rebuilding: %s", exc)

        docs = _load_docs(docs_dir)
        if not docs:
            logger.warning("No .txt files found in RAG docs directory: %s", docs_dir)
            return

        chunks = _build_chunks(docs)
        if not chunks:
            logger.warning("No RAG chunks were produced.")
            return

        try:
            import faiss  # noqa: PLC0415

            embedder = _OllamaEmbedder(
                base_url=ollama_base_url,
                model=embed_model,
            )
            vectors = embedder.encode(
                [chunk["text"] for chunk in chunks],
                normalize_embeddings=True,
            )

            dim = vectors.shape[1]
            index = faiss.IndexFlatIP(dim)
            index.add(vectors)

            cache_dir.mkdir(parents=True, exist_ok=True)
            cache_chunks.write_bytes(pickle.dumps(chunks))
            faiss.write_index(index, str(cache_index))
            cache_meta.write_text(
                json.dumps(
                    {
                        "fingerprint": fingerprint,
                        "model": embed_model,
                    }
                ),
                encoding="utf-8",
            )

            self._chunks = chunks
            self._index = index
            self._embedder = embedder
            self._ready = True
            logger.info("Built RAG index with %d chunks.", len(chunks))
        except Exception as exc:  # noqa: BLE001
            logger.error("RAG build failed: %s", exc)

    def search(
        self,
        query: str,
        max_chunks: int = 5,
        min_score: float = 0.25,
    ) -> list[dict[str, Any]]:
        if not self._ready or not query.strip():
            return []

        if self._index is None or self._embedder is None:
            return []

        try:
            query_vec = self._embedder.encode([query], normalize_embeddings=True)
            scores, indices = self._index.search(query_vec, max_chunks * 2)

            results: list[dict[str, Any]] = []
            for score, idx in zip(scores[0], indices[0]):
                if idx < 0:
                    continue
                if float(score) < min_score:
                    continue

                chunk = dict(self._chunks[idx])
                chunk["score"] = float(score)
                results.append(chunk)

                if len(results) >= max_chunks:
                    break

            return results
        except Exception as exc:  # noqa: BLE001
            logger.error("RAG search failed: %s", exc)
            return []


_ENGINE: RagEngine | None = None


def _get_engine() -> RagEngine:
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = RagEngine()
    return _ENGINE


def build_rag_context(
    query: str,
    max_chunks: int = 5,
    min_score: float = 0.25,
) -> str:
    """
    Return a prompt-friendly RAG context string, or empty string if unavailable.
    """
    results = _get_engine().search(
        query=query,
        max_chunks=max_chunks,
        min_score=min_score,
    )

    if not results:
        return ""

    parts = []
    for item in results:
        source = item.get("source", "unknown")
        text = str(item.get("text", "")).strip()
        if text:
            parts.append(f"[SOURCE: {source}]\n{text}")

    return "\n\n".join(parts)


def rebuild_index() -> bool:
    """
    Force a full rebuild by deleting cache files and recreating the engine.
    """
    global _ENGINE

    try:
        _, _, cache_dir, _, _ = _get_config()
        cache_dir = Path(cache_dir)

        for path in (
            cache_dir / "chunks.pkl",
            cache_dir / "index.faiss",
            cache_dir / "meta.json",
        ):
            try:
                path.unlink(missing_ok=True)
            except Exception:
                pass

        _ENGINE = None
        return _get_engine()._ready
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to rebuild RAG index: %s", exc)
        _ENGINE = None
        return False