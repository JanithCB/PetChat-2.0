"""Main application window for PetChat-2.0."""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation
from PyQt6.QtGui import QCloseEvent
from PyQt6.QtWidgets import QGraphicsOpacityEffect, QMainWindow, QStackedWidget, QWidget

from src.config import APP_NAME, APP_VERSION, DEFAULT_MODE, THEME_COLORS
from src.ui.auth_page import AuthPage
from src.ui.chat_page import ChatPage
from src.ui.model_setup_page import ModelSetupPage


_PAGE_AUTH = 0
_PAGE_MODEL_SETUP = 1
_PAGE_CHAT = 2


class MainWindow(QMainWindow):
    """Coordinates the stacked PetChat pages and session handoff."""

    _PAGE_FADE_MS = 180

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._user_name: str = ""
        self._session_config: dict[str, Any] = {}
        self._current_mode: str = DEFAULT_MODE
        self._fade_animation: QPropertyAnimation | None = None

        self._setup_window()
        self._build_stack()
        self._wire_signals()
        self.go_to_auth()

    def _setup_window(self) -> None:
        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")
        self.setMinimumSize(900, 660)
        self.resize(1040, 780)
        self.setStyleSheet(
            f"""
            QMainWindow {{
                background-color: {THEME_COLORS['background']};
                color: {THEME_COLORS['text']};
            }}
            """
        )

    def _build_stack(self) -> None:
        self._stack = QStackedWidget(self)
        self._stack.setObjectName("mainStack")
        self.setCentralWidget(self._stack)

        self._auth_page = AuthPage()
        self._model_setup_page = ModelSetupPage()
        self._chat_page = ChatPage()

        self._stack.addWidget(self._auth_page)
        self._stack.addWidget(self._model_setup_page)
        self._stack.addWidget(self._chat_page)

    def _wire_signals(self) -> None:
        self._connect_if_present(
            self._auth_page,
            "login_completed",
            self._handle_login_completed,
        )
        self._connect_if_present(
            self._auth_page,
            "login_successful",
            self._handle_legacy_login_successful,
        )

        self._connect_if_present(
            self._model_setup_page,
            "chat_requested",
            self._handle_chat_requested,
        )
        self._connect_if_present(
            self._model_setup_page,
            "setup_confirmed",
            self._handle_legacy_setup_confirmed,
        )

        self._connect_if_present(
            self._chat_page,
            "logout_requested",
            self.go_to_auth,
        )
        self._connect_if_present(
            self._chat_page,
            "back_requested",
            self._back_to_model_setup,
        )

    @staticmethod
    def _connect_if_present(obj: object, signal_name: str, slot: Any) -> None:
        signal = getattr(obj, signal_name, None)
        if signal is not None and hasattr(signal, "connect"):
            signal.connect(slot)

    def _set_page(self, page_index: int, *, fade: bool = True) -> None:
        self._stack.setCurrentIndex(page_index)

        if not fade:
            return

        page = self._stack.currentWidget()
        if page is None:
            return

        effect = QGraphicsOpacityEffect(page)
        page.setGraphicsEffect(effect)

        if self._fade_animation is not None:
            self._fade_animation.stop()

        self._fade_animation = QPropertyAnimation(effect, b"opacity", self)
        self._fade_animation.setDuration(self._PAGE_FADE_MS)
        self._fade_animation.setStartValue(0.0)
        self._fade_animation.setEndValue(1.0)
        self._fade_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade_animation.finished.connect(lambda: page.setGraphicsEffect(None))
        self._fade_animation.start()

    def _handle_login_completed(self, user_name: str) -> None:
        self.go_to_model_setup(user_name)

    def _handle_legacy_login_successful(self, user_id: str, user_name: str) -> None:
        _ = user_id
        self.go_to_model_setup(user_name)

    def _handle_chat_requested(
        self,
        user_name: str,
        mode: str,
        session_config: dict[str, Any],
    ) -> None:
        self.start_chat(user_name, session_config, mode)

    def _handle_legacy_setup_confirmed(self, session_config: dict[str, Any]) -> None:
        config = dict(session_config)

        user_name = str(
            config.pop("user_name", "")
            or config.pop("username", "")
            or self._user_name
        )
        initial_mode = str(config.pop("mode", self._current_mode or DEFAULT_MODE))

        self.start_chat(user_name, config, initial_mode)

    def _back_to_model_setup(self) -> None:
        self.go_to_model_setup(self._user_name)

    def go_to_auth(self) -> None:
        self._user_name = ""
        self._session_config = {}
        self._current_mode = DEFAULT_MODE

        if hasattr(self._auth_page, "reset"):
            self._auth_page.reset()

        if hasattr(self._model_setup_page, "reset"):
            self._model_setup_page.reset()

        if hasattr(self._chat_page, "reset_session"):
            self._chat_page.reset_session()

        self._set_page(_PAGE_AUTH, fade=True)
        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")

    def go_to_model_setup(self, user_name: str) -> None:
        self._user_name = user_name.strip()

        if hasattr(self._model_setup_page, "set_user_name"):
            self._model_setup_page.set_user_name(self._user_name)
        elif hasattr(self._model_setup_page, "set_user"):
            try:
                self._model_setup_page.set_user(self._user_name)
            except TypeError:
                self._model_setup_page.set_user("", self._user_name)

        self._set_page(_PAGE_MODEL_SETUP, fade=True)

        suffix = f" - {self._user_name}" if self._user_name else ""
        self.setWindowTitle(f"{APP_NAME} - Model Setup{suffix}")

    def start_chat(
        self,
        user_name: str,
        session_config: dict[str, Any],
        initial_mode: str,
    ) -> None:
        self._user_name = user_name.strip()
        self._session_config = dict(session_config)
        self._current_mode = initial_mode or DEFAULT_MODE

        if hasattr(self._chat_page, "start_session"):
            try:
                self._chat_page.start_session(
                    user_name=self._user_name,
                    mode=self._current_mode,
                    session_config=self._session_config,
                )
            except TypeError:
                try:
                    self._chat_page.start_session(
                        self._user_name,
                        self._current_mode,
                        self._session_config,
                    )
                except TypeError:
                    user_info = {
                        "user_name": self._user_name,
                        "user_id": self._user_name.lower().replace(" ", "_") or "user",
                        "session_id": "desktop_session",
                    }
                    self._chat_page.start_session(self._session_config, user_info)

        self._set_page(_PAGE_CHAT, fade=True)

        title_user = self._user_name or "Chat"
        self.setWindowTitle(f"{APP_NAME} - {title_user}")

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if hasattr(self._chat_page, "shutdown"):
            self._chat_page.shutdown()

        event.accept()