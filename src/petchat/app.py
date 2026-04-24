"""
app.py -- PetChat-2.0 application entry point.

Responsibilities
----------------
- Bootstrap logging, config, and optional RAG index.
- Expose run_app() for the UI layer and run_cli() for headless testing.
- Centralise startup so every module gets initialised in the right order.

Usage
-----
    # Full app (after UI is wired):
    python -m petchat.app

    # Quick CLI test loop (no UI):
    python -m petchat.app --cli

    # CLI with a specific model:
    python -m petchat.app --cli --model llama3.2:3b
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Ensure src/ is on the path when running as a script
# ---------------------------------------------------------------------------
_SRC = Path(__file__).resolve().parents[1]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

# ---------------------------------------------------------------------------
# Imports (after path fix)
# ---------------------------------------------------------------------------
from petchat.config import LOG_DIR, SUPABASE_ENABLED  # noqa: E402

# ---------------------------------------------------------------------------
# Logging -- file + console
# ---------------------------------------------------------------------------

LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_DIR / "petchat.log", encoding="utf-8"),
    ],
)

for _noisy in ("httpx", "httpcore", "urllib3", "faiss"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)

logger = logging.getLogger("petchat.app")


# ---------------------------------------------------------------------------
# Bootstrap helpers
# ---------------------------------------------------------------------------

def _bootstrap_rag() -> bool:
    try:
        from petchat.rag.rag_engine import _get_engine  # noqa: PLC0415
        engine = _get_engine()
        if engine._ready:
            logger.info("RAG index ready (%d chunks).", len(engine._chunks))
        else:
            logger.info("RAG unavailable -- running without document context.")
        return engine._ready
    except Exception as exc:  # noqa: BLE001
        logger.warning("RAG bootstrap failed: %s", exc)
        return False


def _bootstrap_supabase() -> None:
    if not SUPABASE_ENABLED:
        logger.info("Supabase disabled -- running without long-term memory.")
        return
    try:
        from petchat.memory.supabase_client import get_supabase  # noqa: PLC0415
        client = get_supabase()
        if client:
            logger.info("Supabase connected.")
        else:
            logger.warning("Supabase enabled but client unavailable.")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Supabase bootstrap failed: %s", exc)


def bootstrap() -> None:
    """Run all startup tasks once before any UI or CLI loop."""
    logger.info("PetChat-2.0 starting up...")
    _bootstrap_rag()
    _bootstrap_supabase()
    logger.info("Bootstrap complete.")


# ---------------------------------------------------------------------------
# CLI chat loop (headless test mode)
# ---------------------------------------------------------------------------

def _make_session_config(model: str) -> dict:
    """Build a LocalProvider session_config from a model name string."""
    provider_id = "llama3_2_3b"
    if "mistral" in model.lower():
        provider_id = "mistral_7b"
    elif "llama3:8b" in model.lower():
        provider_id = "llama3_8b"

    return {
        "provider_type": "local",
        "provider_id":   provider_id,
        "model_id":      model,
        "is_local":      True,
        "api_key":       "",
    }


def run_cli(model: str = "llama3.2:3b") -> None:
    """
    Interactive terminal chat loop for verifying the pipeline
    before wiring the PyQt6 UI.

    Commands:
      /quit or /exit  -> stop
      /risk           -> show the last detected risk
      /plan           -> show the last support plan
    """
    from petchat.core.pipeline import run_chat_turn  # noqa: PLC0415

    session_config = _make_session_config(model)
    history: list[dict[str, str]] = []
    user_info = {
        "user_name":  "Dev",
        "user_id":    "cli_user",
        "session_id": "cli_session",
    }

    last_result: dict = {}

    print()
    print("=" * 60)
    print("  PetChat-2.0  --  CLI mode")
    print(f"  Model : {model}")
    print("  Type /quit to exit, /plan for last plan, /risk for risk level")
    print("=" * 60)
    print()

    while True:
        try:
            raw = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break

        if not raw:
            continue

        if raw.lower() in {"/quit", "/exit", "quit", "exit"}:
            print("Goodbye.")
            break

        if raw.lower() == "/plan" and last_result:
            plan = last_result.get("support_plan", {})
            print("\n-- Support Plan --")
            for k, v in plan.items():
                if v not in (None, "", [], {}):
                    print(f"  {k}: {v}")
            print()
            continue

        if raw.lower() == "/risk" and last_result:
            print(f"  Risk: {last_result.get('risk_level')}\n")
            continue

        print("Companion: ...", end="\r", flush=True)
        try:
            result = run_chat_turn(
                session_config=session_config,
                history=history,
                user_message=raw,
                user_info=user_info,
            )
            last_result = result

            reply = result["final_reply"]
            print("Companion: " + " " * 30, end="\r")
            print(f"Companion: {reply}")
            print()

            history.append({"role": "user",      "content": raw})
            history.append({"role": "assistant",  "content": reply})
            if len(history) > 16:
                history = history[-16:]

        except KeyboardInterrupt:
            print("\n(interrupted)")
            break
        except Exception as exc:  # noqa: BLE001
            logger.exception("Pipeline error: %s", exc)
            print(f"Companion: Something went wrong ({exc})\n")


# ---------------------------------------------------------------------------
# GUI entry point
# ---------------------------------------------------------------------------

def run_app() -> None:
    """
    Launch the PyQt6 chat UI.
    Falls back to CLI if the UI module is not ready yet.
    """
    try:
        from petchat.ui.main_window import MainWindow  # noqa: PLC0415
        from PyQt6.QtWidgets import QApplication       # noqa: PLC0415

        app = QApplication(sys.argv)
        window = MainWindow()
        window.show()
        sys.exit(app.exec())
    except ImportError as exc:
        logger.warning("UI not available yet (%s) -- falling back to CLI.", exc)
        run_cli()


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="PetChat-2.0")
    parser.add_argument(
        "--cli",
        action="store_true",
        help="Run headless CLI chat loop (no UI)",
    )
    parser.add_argument(
        "--model",
        default="llama3.2:3b",
        help="Ollama model name (default: llama3.2:3b)",
    )
    parser.add_argument(
        "--no-rag",
        action="store_true",
        help="Skip RAG bootstrap",
    )
    args = parser.parse_args(argv)

    if args.no_rag:
        try:
            import petchat.config as cfg  # noqa: PLC0415
            cfg.RAG_ENABLED = False
        except Exception:
            pass

    bootstrap()

    if args.cli:
        run_cli(model=args.model)
    else:
        run_app()


if __name__ == "__main__":
    main()