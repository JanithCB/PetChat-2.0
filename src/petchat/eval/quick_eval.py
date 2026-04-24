"""
eval/quick_eval.py -- Offline evaluation tool for PetChat-2.0.

Usage
-----
    python -m petchat.eval.quick_eval
    python -m petchat.eval.quick_eval --prompts path/to/eval_prompts.json
    python -m petchat.eval.quick_eval --no-rag   # skip RAG context step
    python -m petchat.eval.quick_eval --verbose   # show full plan dict

Reads eval_prompts.json, runs each case through:
    1. safety.detect_risk_level
    2. esc_support.build_esc_support_plan  (skipped on high-risk)
    3. rag_engine.build_rag_context        (optional, --no-rag to skip)

Prints PASS/FAIL per case and a final summary.
Results are also appended to data/logs/eval.log.

eval_prompts.json schema
------------------------
[
  {
    "id": "tc_001",
    "description": "user expresses hopelessness",
    "user_message": "Nothing will ever get better.",
    "history": [],
    "expect": {
      "risk_level": "medium",
      "stage": "comforting",
      "primary_emotion": "hopelessness",
      "strategies_include": ["reflection_of_feelings"],
      "allow_emoji": false
    }
  },
  ...
]

All "expect" fields are optional; missing fields are skipped.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import textwrap
import time
from datetime import datetime
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Path setup -- allow running as __main__ without package install
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))

from petchat.config import EVAL_PROMPTS_FILE, LOG_DIR          # noqa: E402
from petchat.core import safety, esc_support                   # noqa: E402
from petchat.rag.rag_engine import build_rag_context           # noqa: E402

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

LOG_DIR.mkdir(parents=True, exist_ok=True)
_LOG_FILE = LOG_DIR / "eval.log"

_file_handler = logging.FileHandler(_LOG_FILE, encoding="utf-8")
_file_handler.setFormatter(
    logging.Formatter("%(asctime)s %(levelname)-8s %(message)s")
)

logger = logging.getLogger("petchat.eval")
logger.setLevel(logging.DEBUG)
logger.addHandler(_file_handler)

# ---------------------------------------------------------------------------
# ANSI colours (stripped on non-TTY)
# ---------------------------------------------------------------------------

def _is_tty() -> bool:
    return sys.stdout.isatty()

_GREEN  = "\033[32m" if _is_tty() else ""
_RED    = "\033[31m" if _is_tty() else ""
_YELLOW = "\033[33m" if _is_tty() else ""
_BOLD   = "\033[1m"  if _is_tty() else ""
_RESET  = "\033[0m"  if _is_tty() else ""

PASS_TAG = f"{_GREEN}{_BOLD}PASS{_RESET}"
FAIL_TAG = f"{_RED}{_BOLD}FAIL{_RESET}"
SKIP_TAG = f"{_YELLOW}SKIP{_RESET}"


# ---------------------------------------------------------------------------
# Load prompts
# ---------------------------------------------------------------------------

def load_prompts(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        print(f"eval_prompts.json not found: {path}", file=sys.stderr)
        sys.exit(1)
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, list):
        print("eval_prompts.json must be a JSON array.", file=sys.stderr)
        sys.exit(1)
    return data


# ---------------------------------------------------------------------------
# Single test runner
# ---------------------------------------------------------------------------

def run_case(
    case:    dict[str, Any],
    use_rag: bool,
    verbose: bool,
) -> dict[str, Any]:
    """
    Execute one eval case.

    Returns a result dict:
        id, passed, failures, actual, elapsed_ms
    """
    case_id     = case.get("id", "?")
    user_msg    = case.get("user_message", "")
    history     = case.get("history", [])
    expect      = case.get("expect", {})

    t0 = time.perf_counter()

    # Step 1 -- risk detection
    risk_level, tags = safety.detect_risk_level(user_msg)

    # Step 2 -- support plan (skip on high risk)
    plan: dict[str, Any] = {}
    if risk_level != "high":
        plan = esc_support.build_esc_support_plan(
            history=history,
            user_message=user_msg,
            risk_level=(risk_level, tags),
        )

    # Step 3 -- RAG context (informational only; not checked in expectations)
    rag_snippet = ""
    if use_rag:
        try:
            rag_snippet = build_rag_context(user_msg, max_chunks=2)
        except Exception as exc:  # noqa: BLE001
            rag_snippet = f"[RAG error: {exc}]"

    elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)

    # ------------------------------------------------------------------
    # Assertion checks
    # ------------------------------------------------------------------
    failures: list[str] = []

    def _check(field: str, actual: Any, expected: Any) -> None:
        if expected is None:
            return
        if isinstance(expected, list):
            # "strategies_include" style: check subset membership
            for item in expected:
                if item not in actual:
                    failures.append(
                        f"{field}: expected {item!r} in {actual!r}"
                    )
        elif actual != expected:
            failures.append(f"{field}: expected {expected!r}, got {actual!r}")

    _check("risk_level",    risk_level,                expect.get("risk_level"))
    _check("stage",         plan.get("stage"),          expect.get("stage"))
    _check("primary_emotion", plan.get("primary_emotion"), expect.get("primary_emotion"))
    _check("allow_emoji",   plan.get("allow_emoji"),    expect.get("allow_emoji"))
    _check("response_style", plan.get("response_style"), expect.get("response_style"))
    _check("should_ask_question",
           plan.get("should_ask_question"),
           expect.get("should_ask_question"))
    _check("strategies_include",
           plan.get("strategies", []),
           expect.get("strategies_include"))

    passed = len(failures) == 0

    actual = {
        "risk_level":          risk_level,
        "tags":                tags,
        "stage":               plan.get("stage"),
        "primary_emotion":     plan.get("primary_emotion"),
        "secondary_emotions":  plan.get("secondary_emotions"),
        "distress_intensity":  plan.get("distress_intensity"),
        "strategies":          plan.get("strategies"),
        "allow_emoji":         plan.get("allow_emoji"),
        "response_style":      plan.get("response_style"),
        "should_ask_question": plan.get("should_ask_question"),
        "should_offer_action": plan.get("should_offer_action"),
        "rag_chars":           len(rag_snippet),
    }

    return {
        "id":         case_id,
        "passed":     passed,
        "failures":   failures,
        "actual":     actual,
        "elapsed_ms": elapsed_ms,
        "plan":       plan,
        "verbose":    verbose,
    }


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def _fmt_actual(actual: dict[str, Any]) -> str:
    lines = []
    for key, val in actual.items():
        if val is None or val == [] or val == "":
            continue
        lines.append(f"    {key}: {val}")
    return "\n".join(lines)


def print_result(case: dict[str, Any], result: dict[str, Any]) -> None:
    tag        = PASS_TAG if result["passed"] else FAIL_TAG
    case_id    = result["id"]
    desc       = case.get("description", "")
    elapsed    = result["elapsed_ms"]

    print(f"  [{tag}] {_BOLD}{case_id}{_RESET}  {desc}  ({elapsed} ms)")

    if not result["passed"]:
        for f in result["failures"]:
            print(f"         {_RED}x{_RESET} {f}")

    if result["verbose"] or not result["passed"]:
        print(_fmt_actual(result["actual"]))
        print()


def log_result(case: dict[str, Any], result: dict[str, Any]) -> None:
    status = "PASS" if result["passed"] else "FAIL"
    desc   = case.get("description", "")
    logger.info(
        "%s | %s | %s | %.1f ms | %s",
        status, result["id"], desc, result["elapsed_ms"],
        "; ".join(result["failures"]) if result["failures"] else "ok",
    )
    if result["verbose"]:
        logger.debug("actual: %s", json.dumps(result["actual"]))


def print_summary(
    total:   int,
    passed:  int,
    elapsed: float,
    log_path: Path,
) -> None:
    failed = total - passed
    colour = _GREEN if failed == 0 else _RED
    print()
    print("=" * 60)
    print(
        f"  {_BOLD}Results:{_RESET} "
        f"{colour}{passed}/{total} passed{_RESET}  "
        f"({failed} failed)  --  {elapsed:.1f} ms total"
    )
    print(f"  Log: {log_path}")
    print("=" * 60)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="PetChat-2.0 offline eval runner"
    )
    parser.add_argument(
        "--prompts",
        type=Path,
        default=EVAL_PROMPTS_FILE,
        help="Path to eval_prompts.json",
    )
    parser.add_argument(
        "--no-rag",
        action="store_true",
        help="Skip RAG context step",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print full plan output for every case",
    )
    parser.add_argument(
        "--filter",
        type=str,
        default=None,
        metavar="ID_PREFIX",
        help="Only run cases whose id starts with this prefix",
    )
    args = parser.parse_args(argv)

    cases = load_prompts(args.prompts)

    if args.filter:
        cases = [c for c in cases if str(c.get("id", "")).startswith(args.filter)]
        if not cases:
            print(f"No cases matching --filter {args.filter!r}.")
            return 0

    run_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.info("=== eval run started  %s  (%d cases) ===", run_ts, len(cases))

    print()
    print(f"{_BOLD}PetChat-2.0 Eval{_RESET}  --  {len(cases)} case(s)  --  {run_ts}")
    print(f"  prompts : {args.prompts}")
    print(f"  rag     : {'off' if args.no_rag else 'on'}")
    print()

    t_start  = time.perf_counter()
    total    = 0
    passed   = 0

    for case in cases:
        total += 1
        result = run_case(case, use_rag=not args.no_rag, verbose=args.verbose)
        if result["passed"]:
            passed += 1
        print_result(case, result)
        log_result(case, result)

    elapsed_total = round((time.perf_counter() - t_start) * 1000, 1)
    print_summary(total, passed, elapsed_total, _LOG_FILE)

    logger.info(
        "=== eval run finished: %d/%d passed  %.1f ms ===",
        passed, total, elapsed_total,
    )

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
