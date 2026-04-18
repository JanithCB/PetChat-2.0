import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from rag_engine import build_rag_context

eval_file = Path(__file__).parent / "eval_prompts.json"
items = json.loads(eval_file.read_text(encoding="utf-8"))

for i, item in enumerate(items, start=1):
    query = item["input"]
    context = build_rag_context(query)
    print("=" * 80)
    print(f"TEST {i}")
    print("INPUT:", query)
    print("GOAL :", item["goal"])
    print("RAG  :", context[:1200] if context else "[no context]")
    print()