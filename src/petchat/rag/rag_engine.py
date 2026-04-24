"""
rag/rag_engine.py -- FAISS + Ollama-embeddings RAG engine for PetChat-2.0.

Public API
----------
build_rag_context(query, max_chunks, min_score) -> str
rebuild_index() -> bool
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import pickle
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config (imported lazily to avoid circular imports at module load)
# ---------------------------------------------------------------------------

def _get_config():
    from petchat.config import RAG_DOCS_DIR, RAG_CACHE_DIR, RAG_EMBED_MODEL, RAG_ENABLED
    return RAG_DOCS_DIR, RAG_CACHE_DIR, RAG_EMBED_MODEL, RAG_ENABLED


# ---------------------------------------------------------------------------
# Ollama embedder
# ---------------------------------------------------------------------------

class _OllamaEmbedder:
    """Calls Ollama /api/embeddings to produce float32 numpy vectors."""

    def __init__(self, model: str = "nomic-embed-text") -> None:
        self.model = model

    def encode(
        self,
        texts: list[str],
        normalize_embeddings: bool = True,
        **_: Any,
    ):
        import numpy as np  # noqa: PLC0415
        try:
            import ollama  # noqa: PLC0415
        except ImportError as exc:
            raise ImportError("ollama package not installed: pip install ollama") from exc

        vectors = []
        for text in texts:
            resp = ollama.embeddings(model=self.model, prompt=text)
            vectors.append(resp["embedding"])

        arr = np.array(vectors, dtype="float32")
        if normalize_embeddings and arr.size:
            norms = np.linalg.norm(arr, axis=1, keepdims=True)
            arr = arr / np.where(norms == 0, 1.0, norms)
        return arr


# ---------------------------------------------------------------------------
# Dependency check
# ---------------------------------------------------------------------------

def _deps_available() -> bool:
    try:
        import faiss   # noqa: F401
        import ollama  # noqa: F401
        import numpy   # noqa: F401
        return True
    except ImportError:
        return False


# ---------------------------------------------------------------------------
# Document loading + chunking
# ---------------------------------------------------------------------------

def _load_docs(docs_dir: Path) -> list[dict[str, str]]:
    docs = []
    if not docs_dir.exists():
        logger.warning("RAG docs dir not found: %s", docs_dir)
        return docs
    for path in sorted(docs_dir.glob("*.txt")):
        try:
            text = path.read_text(encoding="utf-8", errors="replace").strip()
            if text:
                docs.append({"source": path.name, "text": text})
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not read %s: %s", path, exc)
    logger.info("Loaded %d documents from %s", len(docs), docs_dir)
    return docs


def _chunk_text(
    text: str,
    source: str,
    chunk_size: int = 400,
    overlap: int = 80,
) -> list[dict[str, str]]:
    words  = text.split()
    chunks = []
    start  = 0
    while start < len(words):
        end   = min(start + chunk_size, len(words))
        chunk = " ".join(words[start:end])
        chunks.append({"source": source, "text": chunk})
        if end == len(words):
            break
        start += chunk_size - overlap
    return chunks


def _build_chunks(docs: list[dict[str, str]]) -> list[dict[str, str]]:
    all_chunks: list[dict[str, str]] = []
    for doc in docs:
        all_chunks.extend(_chunk_text(doc["text"], doc["source"]))
    return all_chunks


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def _doc_fingerprint(docs_dir: Path) -> str:
    h = hashlib.md5()
    for path in sorted(docs_dir.glob("*.txt")):
        h.update(path.name.encode())
        h.update(str(path.stat().st_mtime).encode())
    return h.hexdigest()


# ---------------------------------------------------------------------------
# RagEngine
# ---------------------------------------------------------------------------

class RagEngine:
    """Singleton RAG engine. Built lazily on first use."""

    def __init__(self) -> None:
        self._ready:  bool               = False
        self._chunks: list[dict[str, str]] = []
        self._index:  Any                = None
        self._embedder: _OllamaEmbedder | None = None
        self._build()

    # ------------------------------------------------------------------
    def _build(self) -> None:
        if not _deps_available():
            logger.warning("RAG deps missing (faiss / ollama / numpy). RAG disabled.")
            return

        RAG_DOCS_DIR, RAG_CACHE_DIR, RAG_EMBED_MODEL, RAG_ENABLED = _get_config()

        if not RAG_ENABLED:
            logger.info("RAG_ENABLED=False — skipping index build.")
            return

        cache_chunks = RAG_CACHE_DIR / "chunks.pkl"
        cache_index  = RAG_CACHE_DIR / "index.faiss"
        cache_meta   = RAG_CACHE_DIR / "meta.json"

        fingerprint = _doc_fingerprint(RAG_DOCS_DIR)

        # Try loading from cache
        if cache_chunks.exists() and cache_index.exists() and cache_meta.exists():
            meta = json.loads(cache_meta.read_text())
            if meta.get("fingerprint") == fingerprint and meta.get("model") == RAG_EMBED_MODEL:
                try:
                    import faiss  # noqa: PLC0415
                    self._chunks  = pickle.loads(cache_chunks.read_bytes())
                    self._index   = faiss.read_index(str(cache_index))
                    self._embedder = _OllamaEmbedder(RAG_EMBED_MODEL)
                    self._ready   = True
                    logger.info("RAG index loaded from cache (%d chunks).", len(self._chunks))
                    return
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Cache load failed (%s) — rebuilding.", exc)

        # Build from scratch
        docs   = _load_docs(RAG_DOCS_DIR)
        if not docs:
            logger.warning("No documents found in %s — RAG disabled.", RAG_DOCS_DIR)
            return

        chunks = _build_chunks(docs)
        texts  = [c["text"] for c in chunks]

        try:
            import faiss   # noqa: PLC0415
            import numpy as np  # noqa: PLC0415

            embedder = _OllamaEmbedder(RAG_EMBED_MODEL)
            logger.info("Embedding %d chunks with %s…", len(chunks), RAG_EMBED_MODEL)
            vectors = embedder.encode(texts, normalize_embeddings=True)

            dim   = vectors.shape[1]
            index = faiss.IndexFlatIP(dim)   # inner-product = cosine on normalised vecs
            index.add(vectors)

            # Save cache
            RAG_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            cache_chunks.write_bytes(pickle.dumps(chunks))
            faiss.write_index(index, str(cache_index))
            cache_meta.write_text(json.dumps({"fingerprint": fingerprint, "model": RAG_EMBED_MODEL}))

            self._chunks   = chunks
            self._index    = index
            self._embedder = embedder
            self._ready    = True
            logger.info("RAG index built (%d chunks).", len(chunks))

        except Exception as exc:  # noqa: BLE001
            logger.error("RAG build failed: %s", exc)

    # ------------------------------------------------------------------
    def search(
        self,
        query: str,
        max_chunks: int = 5,
        min_score:  float = 0.25,
    ) -> list[dict[str, str]]:
        if not self._ready or self._index is None or self._embedder is None:
            return []

        try:
            import numpy as np  # noqa: PLC0415
            vec = self._embedder.encode([query], normalize_embeddings=True)
            scores, indices = self._index.search(vec, max_chunks * 2)

            results = []
            for score, idx in zip(scores[0], indices[0]):
                if idx < 0 or float(score) < min_score:
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


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_ENGINE: RagEngine | None = None


def _get_engine() -> RagEngine:
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = RagEngine()
    return _ENGINE


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_rag_context(
    query: str,
    max_chunks: int = 5,
    min_score:  float = 0.25,
) -> str:
    """
    Retrieve relevant wellbeing content and format it for the LLM prompt.
    Returns "" when RAG is unavailable or no chunks meet min_score.
    """
    results = _get_engine().search(query, max_chunks=max_chunks, min_score=min_score)
    if not results:
        return ""
    parts = [f"[SOURCE: {r['source']}]\n{r['text'].strip()}" for r in results]
    return "\n\n".join(parts)


def rebuild_index() -> bool:
    """Force a full index rebuild, ignoring the cache. Returns True on success."""
    global _ENGINE
    _ENGINE = None
    RAG_DOCS_DIR, RAG_CACHE_DIR, RAG_EMBED_MODEL, RAG_ENABLED = _get_config()
    for path in (
        RAG_CACHE_DIR / "chunks.pkl",
        RAG_CACHE_DIR / "index.faiss",
        RAG_CACHE_DIR / "meta.json",
    ):
        try:
            path.unlink(missing_ok=True)
        except Exception:  # noqa: BLE001
            pass
    return _get_engine()._ready