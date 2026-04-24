"""
rag/retriever.py — Import alias so pipeline can use:
    from petchat.rag.retriever import build_rag_context
"""
from petchat.rag.rag_engine import build_rag_context, rebuild_index  # noqa: F401