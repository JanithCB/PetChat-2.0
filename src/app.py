"""
app.py -- PetChat-2.0 application entry point.

Responsibilities
----------------
- Configure logging.
- Bootstrap optional services such as RAG and Supabase.
- Expose run_app() for the PyQt6 UI and run_cli() for headless testing.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Ensure project root is importable when running this file directly
# ---------------------------------------------------------------------------

_SRC_ROOT = Path(__file__).resolve().parent
_PROJECT_ROOT = _SRC_ROOT.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


# ---------------------------------------------------------------------------
# Imports after path fix
# ---------------------------------------------------------------------------

import src.config as cfg


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def _configure_logging() -> None:
    cfg.LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(cfg.LOG_DIR / "petchat.log", encoding="utf-8"),
        ],
        force=True,
    )
    for noisy_name in ("httpx", "httpcore", "urllib3", "faiss"):
        logging.getLogger(noisy_name).setLevel(logging.WARNING)


_configure_logging()
logger = logging.getLogger("src.app")


# ---------------------------------------------------------------------------
# Bootstrap helpers
# ---------------------------------------------------------------------------

def _bootstrap_rag() -> bool:
    if not cfg.RAG_ENABLED:
        logger.info("RAG disabled by configuration.")
        return False

    try:
        from src.rag.rag_engine import _get_engine

        engine = _get_engine()
        ready = bool(getattr(engine, "_ready", False))
        chunks = len(getattr(engine, "_chunks", []))

        if ready:
            logger.info("RAG index ready (%d chunks).", chunks)
        else:
            logger.info("RAG unavailable -- running without document context.")
        return ready
    except Exception as exc:
        logger.warning("RAG bootstrap failed: %s", exc)
        return False


def _bootstrap_supabase() -> None:
    if not cfg.USE_SUPABASE_MEMORY:
        logger.info("Supabase disabled -- running without long-term memory.")
        return

    try:
        from src.memory.supabase_client import get_supabase

        client = get_supabase()
        if client is not None:
            logger.info("Supabase connected.")
        else:
            logger.warning("Supabase enabled but client unavailable.")
    except Exception as exc:
        logger.warning("Supabase bootstrap failed: %s", exc)


def bootstrap() -> None:
    logger.info("%s %s starting up...", cfg.APP_NAME, cfg.APP_VERSION)
    _bootstrap_rag()
    _bootstrap_supabase()
    logger.info("Bootstrap complete.")


# ---------------------------------------------------------------------------
# CLI helpers
# ---------------------------------------------------------------------------

def _make_session_config(model: str) -> dict[str, object]:
    normalized = model.strip().lower()

    if normalized in {"phi4-mini", "phi4-mini:latest", "phi4_mini"}:
        provider_id = "phi4_mini"
        model_id = cfg.LOCAL_PROVIDERS[provider_id]
    elif normalized in {"llama3.2:3b", "llama3_2_3b"}:
        provider_id = "llama3_2_3b"
        model_id = cfg.LOCAL_PROVIDERS[provider_id]
    else:
        provider_id = cfg.DEFAULT_LOCAL_PROVIDER
        model_id = model.strip() or cfg.LOCAL_PROVIDERS[provider_id]

    return {
        "provider_type": "local",
        "provider_id": provider_id,
        "model_id": model_id,
        "is_local": True,
        "base_url": cfg.OLLAMA_BASE_URL,
        "api_key": "",
    }


def _trim_history(history: list[dict[str, str]]) -> list[dict[str, str]]:
    max_messages = max(2, cfg.MAX_HISTORY_TURNS * 2)
    if len(history) <= max_messages:
        return history
    return history[-max_messages:]


# ---------------------------------------------------------------------------
# CLI chat loop
# ---------------------------------------------------------------------------

def run_cli(model: str = "llama3.2:3b") -> None:
    from src.core.pipeline import run_chat_turn

    session_config = _make_session_config(model)
    history: list[dict[str, str]] = []
    current_mode = cfg.DEFAULT_MODE
    last_result: dict[str, object] = {}
    user_info = {
        "user_name": "Dev",
        "user_id": "cli_user",
        "session_id": "cli_session",
    }

    print()
    print("=" * 60)
    print(f"  {cfg.APP_NAME}-{cfg.APP_VERSION}  --  CLI mode")
    print(f"  Model : {session_config['model_id']}")
    print("  Mode  : get_support")
    print("  Commands: /quit, /plan, /risk, /mode support, /mode help")
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

        lowered = raw.lower()
        if lowered in {"/quit", "/exit", "quit", "exit"}:
            print("Goodbye.")
            break

        if lowered == "/plan" and last_result:
            plan = last_result.get("support_plan", {})
            print("\n-- Support Plan --")
            if isinstance(plan, dict):
                for key, value in plan.items():
                    if value not in (None, "", [], {}):
                        print(f"  {key}: {value}")
            print()
            continue

        if lowered == "/risk" and last_result:
            print(f"  Risk: {last_result.get('risk_level', 'unknown')}\n")
            continue

        if lowered in {"/mode support", "/mode get_support"}:
            current_mode = cfg.MODE_GET_SUPPORT
            print("Mode switched to get_support.\n")
            continue

        if lowered in {"/mode help", "/mode help_someone"}:
            current_mode = cfg.MODE_HELP_SOMEONE
            print("Mode switched to help_someone.\n")
            continue

        print("Companion: ...", end="\r", flush=True)
        try:
            result = run_chat_turn(
                mode=current_mode,
                session_config=session_config,
                history=history,
                user_message=raw,
                user_info=user_info,
            )
            last_result = result
            reply = str(result.get("final_reply", ""))

            print("Companion: " + " " * 40, end="\r")
            print(f"Companion: {reply}")
            print()

            history.append({"role": "user", "content": raw})
            history.append({"role": "assistant", "content": reply})
            history = _trim_history(history)

        except KeyboardInterrupt:
            print("\n(interrupted)")
            break
        except Exception as exc:
            logger.exception("Pipeline error: %s", exc)
            print("Companion: Something went wrong on my end. Please try again in a moment.\n")


# ---------------------------------------------------------------------------
# GUI entry point
# ---------------------------------------------------------------------------

def run_app() -> None:
    try:
        from PyQt6.QtWidgets import QApplication
        from src.ui.main_window import MainWindow
        from src.ui.styles import apply_app_style

        app = QApplication(sys.argv)
        app.setApplicationName(cfg.APP_NAME)
        apply_app_style(app)

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
    parser = argparse.ArgumentParser(description=f"{cfg.APP_NAME} {cfg.APP_VERSION}")
    parser.add_argument(
        "--cli",
        action="store_true",
        help="Run headless CLI chat loop instead of the desktop UI.",
    )
    parser.add_argument(
        "--model",
        default=cfg.LOCAL_PROVIDERS.get(cfg.DEFAULT_LOCAL_PROVIDER, "llama3.2:3b"),
        help="Local Ollama model name to use in CLI mode.",
    )
    parser.add_argument(
        "--no-rag",
        action="store_true",
        help="Skip RAG bootstrap for this run.",
    )
    args = parser.parse_args(argv)

    if args.no_rag:
        cfg.RAG_ENABLED = False

    bootstrap()

    if args.cli:
        run_cli(model=args.model)
    else:
        run_app()


if __name__ == "__main__":
    main()