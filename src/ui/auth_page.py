"""
ui/auth_page.py — Authentication / identity page for PetChat-2.0.

Collects a username (nickname) and an optional passphrase.
On success emits login_successful(user_id: str, username: str).
MainWindow listens to this signal and transitions to ModelSetupPage.

Supabase user creation / lookup happens here so that every subsequent
page already has a valid user_id to attach sessions to.
"""

from __future__ import annotations

import hashlib
import uuid
from typing import Any

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QFont, QKeyEvent
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)

from petchat.config import APP_NAME, THEME_COLORS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _derive_user_id(username: str, passphrase: str) -> str:
    """
    Deterministic user_id: SHA-256(username + passphrase) → UUID v5 namespace.
    Keeps the ID stable across sessions without a database round-trip when
    Supabase is disabled.  When Supabase IS enabled, the pipeline layer may
    upsert and replace this with the database primary key.
    """
    raw = f"{username.strip().lower()}:{passphrase}".encode()
    digest = hashlib.sha256(raw).hexdigest()
    # Fold into a UUID for a canonical string form.
    return str(uuid.UUID(digest[:32]))


def _validate_username(text: str) -> str | None:
    """Return an error string, or None if the username is acceptable."""
    stripped = text.strip()
    if not stripped:
        return "Please enter a name."
    if len(stripped) < 2:
        return "Name must be at least 2 characters."
    if len(stripped) > 40:
        return "Name must be 40 characters or fewer."
    return None


# ---------------------------------------------------------------------------
# AuthPage
# ---------------------------------------------------------------------------

class AuthPage(QWidget):
    """
    Login / identity page.

    Signals
    -------
    login_successful(user_id: str, username: str)
        Emitted after basic validation passes.
    """

    login_successful = pyqtSignal(str, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()
        self._apply_styles()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Vertical centering
        root.addSpacerItem(QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))

        # Card frame
        card = QFrame()
        card.setObjectName("authCard")
        card.setFixedWidth(400)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(40, 40, 40, 40)
        card_layout.setSpacing(20)

        # App name / header
        title = QLabel(APP_NAME)
        title.setObjectName("authTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(title)

        subtitle = QLabel("Your personal companion. Tell me your name.")
        subtitle.setObjectName("authSubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setWordWrap(True)
        card_layout.addWidget(subtitle)

        card_layout.addSpacing(8)

        # Username field
        self._name_label = QLabel("Your name or nickname")
        self._name_label.setObjectName("fieldLabel")
        card_layout.addWidget(self._name_label)

        self._name_input = QLineEdit()
        self._name_input.setObjectName("authInput")
        self._name_input.setPlaceholderText("e.g. Alex")
        self._name_input.setMaxLength(40)
        self._name_input.returnPressed.connect(self._on_continue)
        card_layout.addWidget(self._name_input)

        # Passphrase field (optional — secures the deterministic user_id)
        self._pass_label = QLabel("Passphrase  (optional — keeps your history private)")
        self._pass_label.setObjectName("fieldLabel")
        card_layout.addWidget(self._pass_label)

        self._pass_input = QLineEdit()
        self._pass_input.setObjectName("authInput")
        self._pass_input.setPlaceholderText("Leave blank for a public session")
        self._pass_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._pass_input.returnPressed.connect(self._on_continue)
        card_layout.addWidget(self._pass_input)

        # Error label (hidden until needed)
        self._error_label = QLabel("")
        self._error_label.setObjectName("errorLabel")
        self._error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._error_label.setWordWrap(True)
        self._error_label.hide()
        card_layout.addWidget(self._error_label)

        card_layout.addSpacing(4)

        # Continue button
        self._continue_btn = QPushButton("Continue")
        self._continue_btn.setObjectName("continueBtn")
        self._continue_btn.setFixedHeight(44)
        self._continue_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._continue_btn.clicked.connect(self._on_continue)
        card_layout.addWidget(self._continue_btn)

        # Centre the card horizontally
        h_wrap = QHBoxLayout()
        h_wrap.addSpacerItem(QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))
        h_wrap.addWidget(card)
        h_wrap.addSpacerItem(QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))

        root.addLayout(h_wrap)
        root.addSpacerItem(QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))

    def _apply_styles(self) -> None:
        bg  = THEME_COLORS["background"]
        acc = THEME_COLORS["accent"]
        inp = THEME_COLORS["input_bg"]
        txt = THEME_COLORS["bot_bubble_text"]
        muted = THEME_COLORS["status_text"]
        div   = THEME_COLORS["divider"]

        self.setStyleSheet(
            f"""
            AuthPage {{
                background-color: {bg};
            }}

            QFrame#authCard {{
                background-color: #0D0D0D;
                border: 1px solid {div};
                border-radius: 12px;
            }}

            QLabel#authTitle {{
                color: {acc};
                font-size: 26px;
                font-weight: 700;
                letter-spacing: 1px;
            }}

            QLabel#authSubtitle {{
                color: {muted};
                font-size: 13px;
            }}

            QLabel#fieldLabel {{
                color: {muted};
                font-size: 12px;
                font-weight: 500;
            }}

            QLineEdit#authInput {{
                background-color: {inp};
                color: {txt};
                border: 1px solid {div};
                border-radius: 6px;
                padding: 10px 12px;
                font-size: 14px;
                selection-background-color: {acc};
                selection-color: #000000;
            }}

            QLineEdit#authInput:focus {{
                border: 1.5px solid {acc};
            }}

            QLabel#errorLabel {{
                color: #FF6B6B;
                font-size: 12px;
                min-height: 16px;
            }}

            QPushButton#continueBtn {{
                background-color: {acc};
                color: #000000;
                border: none;
                border-radius: 6px;
                font-size: 15px;
                font-weight: 600;
                letter-spacing: 0.5px;
            }}

            QPushButton#continueBtn:hover {{
                background-color: #FFE57A;
            }}

            QPushButton#continueBtn:pressed {{
                background-color: #F0C030;
            }}

            QPushButton#continueBtn:disabled {{
                background-color: #555555;
                color: #999999;
            }}
            """
        )

    # ------------------------------------------------------------------
    # Slot: Continue pressed / Enter key
    # ------------------------------------------------------------------

    def _on_continue(self) -> None:
        self._clear_error()

        username  = self._name_input.text().strip()
        passphrase = self._pass_input.text()

        error = _validate_username(username)
        if error:
            self._show_error(error)
            self._name_input.setFocus()
            return

        self._continue_btn.setEnabled(False)
        self._continue_btn.setText("Connecting...")

        user_id = _derive_user_id(username, passphrase)
        self.login_successful.emit(user_id, username)

    # ------------------------------------------------------------------
    # Error helpers
    # ------------------------------------------------------------------

    def _show_error(self, message: str) -> None:
        self._error_label.setText(message)
        self._error_label.show()

    def _clear_error(self) -> None:
        self._error_label.setText("")
        self._error_label.hide()

    # ------------------------------------------------------------------
    # Public API used by MainWindow
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Clear all inputs and restore the button — called on logout."""
        self._name_input.clear()
        self._pass_input.clear()
        self._clear_error()
        self._continue_btn.setEnabled(True)
        self._continue_btn.setText("Continue")
        self._name_input.setFocus()
