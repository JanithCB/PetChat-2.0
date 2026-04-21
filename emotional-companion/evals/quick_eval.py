import json
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


from rag_engine import build_rag_context
from safety import detect_risk_level, build_safety_reply
from esc_support import build_esc_support_plan


EMOJIS = ["🙂", "😊", "☺️", "🤗", "🫂", "😥", "😓", "😑", "😒", "😬", "🤢"]


# -------------------------
# HELPERS
# -------------------------

def parse_risk_result(result):
    if isinstance(result, tuple):
        return (result[0] or "none", result[1] or [])
    if isinstance(result, str):
        return result, []
    return "none", []


def contains_emoji(text: str) -> bool:
    return any(e in (text or "") for e in EMOJIS)


def question_count(text: str) -> int:
    return (text or "").count("?")


def is_too_long(text: str, max_sentences=6):
    return len([s for s in text.split(".") if s.strip()]) > max_sentences


def has_repetitive_phrases(text: str):
    patterns = [
        "that feels",
        "i understand",
        "that sounds",
    ]
    lowered = text.lower()
    return any(p in lowered for p in patterns)


def print_check(label: str, passed: bool, detail: str = ""):
    status = "PASS" if passed else "FAIL"
    print(f"{label:<25}: {status}" + (f" ({detail})" if detail else ""))


# -------------------------
# MAIN EVAL
# -------------------------

def run_eval():
    eval_file = Path(__file__).parent / "eval_prompts.json"
    items = json.loads(eval_file.read_text(encoding="utf-8"))

    total, passed = 0, 0

    for i, item in enumerate(items, 1):
        total += 1
        case_pass = True

        query = item["input"]
        expected_risk = item.get("expected_risk")

        print("=" * 90)
        print(f"TEST {i}")
        print("INPUT:", query)

        # ---- Risk ----
        risk_level, risk_tags = parse_risk_result(detect_risk_level(query))
        print("RISK:", risk_level)

        if expected_risk:
            ok = risk_level == expected_risk
            print_check("Risk match", ok)
            case_pass &= ok

        # ---- Plan ----
        support_plan = None
        if risk_level != "high":
            support_plan = build_esc_support_plan(
                history=[],
                user_message=query,
                risk_level=risk_level,
            )

        if support_plan:
            print("EMOTION:", support_plan.get("primary_emotion"))
            print("STAGE  :", support_plan.get("stage"))

        # ---- RAG ----
        if risk_level != "high":
            try:
                rag_context = build_rag_context(query)
                ok = rag_context is not None
                print_check("RAG context", ok)
                case_pass &= ok
            except Exception as e:
                print("RAG ERROR:", e)
                case_pass = False

        # ---- Safety Reply ----
        if risk_level == "high":
            reply = build_safety_reply(risk_level=risk_level)

            print("REPLY:", reply)

            # basic safety checks
            ok = question_count(reply) <= 2
            print_check("Question limit", ok)
            case_pass &= ok

            ok = not contains_emoji(reply)
            print_check("No emoji", ok)
            case_pass &= ok

            ok = not is_too_long(reply)
            print_check("Not too long", ok)
            case_pass &= ok

        # ---- Style sanity checks (NEW 🔥) ----
        if item.get("sample_reply"):
            reply = item["sample_reply"]

            print("STYLE CHECK ON SAMPLE REPLY")

            ok = not is_too_long(reply)
            print_check("Length natural", ok)
            case_pass &= ok

            ok = question_count(reply) <= 2
            print_check("Question natural", ok)
            case_pass &= ok

            ok = not has_repetitive_phrases(reply)
            print_check("Not generic", ok)
            case_pass &= ok

        print("RESULT:", "PASS" if case_pass else "FAIL", "\n")

        if case_pass:
            passed += 1

    print("=" * 90)
    print(f"FINAL: {passed}/{total} passed")

    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    run_eval()