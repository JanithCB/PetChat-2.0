import json
import hashlib
import re
from pathlib import Path
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer


APP_DIR = Path(__file__).resolve().parent
CACHE_DIR = APP_DIR / "data" / "rag_cache"

RAG_DOCS_DIR = Path(r"D:\HND NIBM\PetChat-2.0\cleaned_txt")
EMBED_MODEL_NAME = "all-MiniLM-L6-v2"

CHUNK_SIZE = 900
CHUNK_OVERLAP = 180
TOP_K = 4
MIN_SCORE = 0.20
MIN_TOP_SCORE = 0.28
MAX_CONTEXT_CHUNKS = 3

INDEX_FILE = CACHE_DIR / "rag_index.faiss"
META_FILE = CACHE_DIR / "rag_meta.json"
STATE_FILE = CACHE_DIR / "rag_state.json"


SOURCE_BOOSTS = {
    "grounding": {
        "who_doing_what_matters.txt": 0.08,
        "va_calmer_life.txt": 0.04,
    },
    "anxiety": {
        "va_calmer_life.txt": 0.07,
        "anxiety_depression_reduction.txt": 0.06,
        "who_doing_what_matters.txt": 0.04,
    },
    "depression": {
        "va_brief_cbt_depression.txt": 0.07,
        "northwestern_cbt_workbook.txt": 0.06,
        "anxiety_depression_reduction.txt": 0.04,
    },
    "lonely": {
        "northwestern_cbt_workbook.txt": 0.05,
        "va_brief_cbt_depression.txt": 0.04,
    },
    "crisis": {
        "sri_lanka_support_resources.txt": 0.20,
    },
}


class LocalRAG:
    def __init__(self, docs_dir):
        self.docs_dir = Path(docs_dir)
        self.embedder = SentenceTransformer(EMBED_MODEL_NAME)
        self.index = None
        self.chunks = []
        self.metadata = []

        CACHE_DIR.mkdir(parents=True, exist_ok=True)

        if self._can_use_cache():
            self._load_cache()
        else:
            self._build_index()
            self._save_cache()

    def _clean_text(self, text: str) -> str:
        text = text.replace("\u00ad", "")
        text = text.replace("\ufeff", "")
        text = re.sub(r"\r\n?", "\n", text)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def _chunk_text(self, text: str, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
        text = self._clean_text(text)
        if not text:
            return []

        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        chunks = []
        current = ""

        for para in paragraphs:
            proposed = f"{current}\n\n{para}".strip() if current else para

            if len(proposed) <= chunk_size:
                current = proposed
                continue

            if current:
                chunks.append(current)

            if len(para) <= chunk_size:
                current = para
            else:
                start = 0
                step = max(1, chunk_size - overlap)
                while start < len(para):
                    piece = para[start:start + chunk_size].strip()
                    if len(piece) >= 80:
                        chunks.append(piece)
                    start += step
                current = ""

        if current and len(current) >= 80:
            chunks.append(current)

        return chunks

    def _get_doc_state(self):
        if not self.docs_dir.exists():
            raise FileNotFoundError(f"RAG docs folder not found: {self.docs_dir}")

        txt_files = sorted(self.docs_dir.glob("*.txt"))
        if not txt_files:
            raise FileNotFoundError(f"No .txt files found in: {self.docs_dir}")

        docs = []
        for file_path in txt_files:
            data = file_path.read_bytes()
            docs.append(
                {
                    "name": file_path.name,
                    "size": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                }
            )

        return {
            "docs_dir": str(self.docs_dir),
            "embed_model": EMBED_MODEL_NAME,
            "chunk_size": CHUNK_SIZE,
            "chunk_overlap": CHUNK_OVERLAP,
            "docs": docs,
        }

    def _can_use_cache(self):
        if not INDEX_FILE.exists() or not META_FILE.exists() or not STATE_FILE.exists():
            return False

        try:
            current_state = self._get_doc_state()
            saved_state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            return current_state == saved_state
        except Exception:
            return False

    def _build_index(self):
        txt_files = sorted(self.docs_dir.glob("*.txt"))

        all_chunks = []
        all_meta = []

        for file_path in txt_files:
            text = file_path.read_text(encoding="utf-8", errors="ignore")
            chunks = self._chunk_text(text)

            for i, chunk in enumerate(chunks):
                all_chunks.append(chunk)
                all_meta.append(
                    {
                        "source": file_path.name,
                        "chunk_id": i,
                    }
                )

        if not all_chunks:
            raise ValueError("No valid text chunks were created from the RAG documents.")

        embeddings = self.embedder.encode(
            all_chunks,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        ).astype("float32")

        dim = embeddings.shape[1]
        index = faiss.IndexFlatIP(dim)
        index.add(embeddings)

        self.index = index
        self.chunks = all_chunks
        self.metadata = all_meta

    def _save_cache(self):
        faiss.write_index(self.index, str(INDEX_FILE))

        payload = {
            "chunks": self.chunks,
            "metadata": self.metadata,
        }
        META_FILE.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        state = self._get_doc_state()
        STATE_FILE.write_text(
            json.dumps(state, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    def _load_cache(self):
        self.index = faiss.read_index(str(INDEX_FILE))

        payload = json.loads(META_FILE.read_text(encoding="utf-8"))
        self.chunks = payload.get("chunks", [])
        self.metadata = payload.get("metadata", [])

        if self.index is None or not self.chunks:
            raise ValueError("Cached RAG data is invalid.")

    def _detect_query_tags(self, query: str):
        q = query.lower()
        tags = set()

        grounding_words = ["ground", "grounding", "calm down", "overwhelmed", "panic", "breathe", "breathing"]
        anxiety_words = ["anxious", "anxiety", "worry", "worried", "panic", "stress", "tense"]
        depression_words = ["depressed", "empty", "hopeless", "worthless", "sad", "stuck", "numb"]
        lonely_words = ["lonely", "alone", "no one", "isolated"]
        crisis_words = ["suicide", "kill myself", "want to die", "hurt myself", "self-harm", "end my life"]

        if any(word in q for word in grounding_words):
            tags.add("grounding")
        if any(word in q for word in anxiety_words):
            tags.add("anxiety")
        if any(word in q for word in depression_words):
            tags.add("depression")
        if any(word in q for word in lonely_words):
            tags.add("lonely")
        if any(word in q for word in crisis_words):
            tags.add("crisis")

        return tags

    def _apply_source_boost(self, query: str, results: list):
        tags = self._detect_query_tags(query)
        if not tags:
            return results

        boosted = []
        for item in results:
            boost = 0.0
            for tag in tags:
                boost += SOURCE_BOOSTS.get(tag, {}).get(item["source"], 0.0)

            updated = dict(item)
            updated["boost"] = boost
            updated["final_score"] = updated["score"] + boost
            boosted.append(updated)

        boosted.sort(key=lambda x: x["final_score"], reverse=True)
        return boosted

    def search(self, query: str, top_k=TOP_K):
        query = (query or "").strip()
        if not query or self.index is None:
            return []

        query_embedding = self.embedder.encode(
            [query],
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        ).astype("float32")

        scores, indices = self.index.search(query_embedding, top_k)

        results = []
        seen = set()

        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:
                continue
            if float(score) < MIN_SCORE:
                continue

            chunk_text = self.chunks[idx].strip()
            source = self.metadata[idx]["source"]
            chunk_id = self.metadata[idx]["chunk_id"]

            key = (source, chunk_id)
            if key in seen:
                continue
            seen.add(key)

            results.append(
                {
                    "score": float(score),
                    "text": chunk_text,
                    "source": source,
                    "chunk_id": chunk_id,
                }
            )

        if not results:
            return []

        results = self._apply_source_boost(query, results)

        top_score = results[0].get("final_score", results[0]["score"])
        if top_score < MIN_TOP_SCORE:
            return []

        return results[:MAX_CONTEXT_CHUNKS]


_RAG_INSTANCE = None


def get_rag():
    global _RAG_INSTANCE
    if _RAG_INSTANCE is None:
        _RAG_INSTANCE = LocalRAG(RAG_DOCS_DIR)
    return _RAG_INSTANCE


def build_rag_context(query: str) -> str:
    rag = get_rag()
    hits = rag.search(query, top_k=TOP_K)

    if not hits:
        return ""

    blocks = []
    used_sources = []

    for i, hit in enumerate(hits, start=1):
        source = hit["source"]
        chunk_text = hit["text"].strip()
        score = hit.get("final_score", hit["score"])

        if not chunk_text:
            continue

        if source not in used_sources:
            used_sources.append(source)

        blocks.append(
            f"[Source {i}: {source} | score={score:.3f}]\n{chunk_text}"
        )

    if not blocks:
        return ""

    sources_line = "Sources used: " + ", ".join(used_sources)
    return sources_line + "\n\n" + "\n\n".join(blocks)


def debug_search(query: str):
    rag = get_rag()
    hits = rag.search(query, top_k=TOP_K)
    if not hits:
        return []

    return [
        {
            "source": hit["source"],
            "chunk_id": hit["chunk_id"],
            "score": round(hit["score"], 4),
            "final_score": round(hit.get("final_score", hit["score"]), 4),
            "preview": hit["text"][:220].replace("\n", " "),
        }
        for hit in hits
    ]


if __name__ == "__main__":
    try:
        rag = get_rag()
        print(f"Loaded {len(rag.chunks)} chunks.")
        print(json.dumps(debug_search("I feel overwhelmed and need grounding"), indent=2, ensure_ascii=False))
        print()
        print(build_rag_context("I feel lonely and anxious and I need support."))
    except Exception as e:
        print(f"RAG error: {e}")