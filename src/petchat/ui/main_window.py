"""
ui/main_window.py — Top-level application window for PetChat-2.0.

Manages a QStackedWidget with three pages:
    0 — AuthPage        (login / signup)
    1 — ModelSetupPage  (cloud vs local, model picker)
    2 — ChatPage        (WhatsApp-style chat)

Navigation always flows forward:  Auth → ModelSetup → Chat.
show_login() is also available so the logout path can reset the stack.
"""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QCloseEvent, QIcon
from PyQt6.QtWidgets import QMainWindow, QStackedWidget, QWidget

from petchat.config import APP_NAME, APP_VERSION, THEME_COLORS
from petchat.ui.auth_page import AuthPage
from petchat.ui.chat_page import ChatPage
from petchat.ui.model_setup_page import ModelSetupPage


# ---------------------------------------------------------------------------
# Page indices — use these constants instead of raw ints everywhere.
# ---------------------------------------------------------------------------

_PAGE_AUTH        = 0
_PAGE_MODEL_SETUP = 1
_PAGE_CHAT        = 2


class MainWindow(QMainWindow):
    """
    Root window.  Owns the page stack and routes signals between pages.

    Lifecycle
    ---------
    1.  App starts  → show_login()  (AuthPage visible)
    2.  Login OK    → show_model_setup(user_id, username)
    3.  Model OK    → show_chat(session_config, user)
    4.  Logout      → show_login()  (stack fully reset)
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._setup_window()

        # Central stacked widget — pages are added in fixed order.
        self._stack = QStackedWidget()
        self.setCentralWidget(self._stack)

        # Instantiate all three pages once; they are hidden until needed.
        self._auth_page        = AuthPage()
        self._model_setup_page = ModelSetupPage()
        self._chat_page        = ChatPage()

        self._stack.insertWidget(_PAGE_AUTH,        self._auth_page)
        self._stack.insertWidget(_PAGE_MODEL_SETUP, self._model_setup_page)
        self._stack.insertWidget(_PAGE_CHAT,        self._chat_page)

        self._wire_signals()

        # Start on the login page.
        self.show_login()

    # ------------------------------------------------------------------
    # Window setup
    # ------------------------------------------------------------------

    def _setup_window(self) -> None:
        self.setWindowTitle(f"{APP_NAME}  {APP_VERSION}")
        self.setMinimumSize(760, 600)
        self.resize(900, 680)
        self._apply_base_style()

    def _apply_base_style(self) -> None:
        bg  = THEME_COLORS["background"]
        acc = THEME_COLORS["accent"]
        self.setStyleSheet(
            f"""
            QMainWindow, QWidget {{
                background-color: {bg};
                color: {THEME_COLORS["bot_bubble_text"]};
                font-family: 'Segoe UI', 'SF Pro Text', 'Helvetica Neue', Arial, sans-serif;
                font-size: 14px;
            }}
            QScrollBar:vertical {{
                background: {bg};
                width: 6px;
                border-radius: 3px;
            }}
            QScrollBar::handle:vertical {{
                background: #333333;
                border-radius: 3px;
                min-height: 30px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {acc};
            }}
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QScrollBar:horizontal {{
                height: 0px;
            }}
            """
        )

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------

    def _wire_signals(self) -> None:
        """Connect child-page signals to navigation slots."""

        # AuthPage emits login_successful(user_id: str, username: str)
        self._auth_page.login_successful.connect(self._on_login_successful)

        # ModelSetupPage emits setup_confirmed(session_config: dict)
        self._model_setup_page.setup_confirmed.connect(self._on_model_setup_confirmed)

        # ChatPage emits logout_requested()
        self._chat_page.logout_requested.connect(self.show_login)

    # ------------------------------------------------------------------
    # Internal slots
    # ------------------------------------------------------------------

    def _on_login_successful(self, user_id: str, username: str) -> None:
        self.show_model_setup(user_id, username)

    def _on_model_setup_confirmed(self, session_config: dict[str, Any]) -> None:
        # ModelSetupPage must attach user info to session_config before emitting.
        user = {
            "user_id":  session_config.pop("user_id",  ""),
            "username": session_config.pop("username", ""),
        }
        self.show_chat(session_config, user)

    # ------------------------------------------------------------------
    # Public navigation helpers
    # ------------------------------------------------------------------

    def show_login(self) -> None:
        """Reset to the authentication page (also used for logout)."""
        self._auth_page.reset()
        self._stack.setCurrentIndex(_PAGE_AUTH)
        self.setWindowTitle(f"{APP_NAME}  {APP_VERSION}")

    def show_model_setup(self, user_id: str, username: str) -> None:
        """Switch to the model-selection page, injecting user context."""
        self._model_setup_page.set_user(user_id, username)
        self._stack.setCurrentIndex(_PAGE_MODEL_SETUP)
        self.setWindowTitle(f"{APP_NAME}  —  Choose your model")

    def show_chat(
        self,
        session_config: dict[str, Any],
        user: dict[str, str],
    ) -> None:
        """
        Initialise and switch to ChatPage.

        Parameters
        ----------
        session_config:
            Dict produced by ModelSetupPage; must contain at minimum:
                provider_id : str   — stable provider key from config.py
                model_id    : str   — full model string
                is_local    : bool  — True for Ollama, False for cloud
        user:
            Dict with 'user_id' and 'username'.
        """
        self._chat_page.start_session(session_config, user)
        self._stack.setCurrentIndex(_PAGE_CHAT)
        username = user.get("username", "")
        self.setWindowTitle(
            f"{APP_NAME}  —  {username}" if username else APP_NAME
        )

    # ------------------------------------------------------------------
    # Qt overrides
    # ------------------------------------------------------------------

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        """Cleanly shut down the chat pipeline before the window closes."""
        self._chat_page.shutdown()
        event.accept()
