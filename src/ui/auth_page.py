"""Simple name-entry auth page for PetChat-2.0."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)

from src.config import APP_NAME
from src.ui.styles import C, CARD, INPUT, PRIMARY_BTN


class AuthPage(QWidget):
    login_completed = pyqtSignal(str)
    login_successful = pyqtSignal(str, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()
        self.reset()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 32, 32, 32)
        root.setSpacing(0)
        root.addItem(
            QSpacerItem(
                20,
                20,
                QSizePolicy.Policy.Minimum,
                QSizePolicy.Policy.Expanding,
            )
        )

        center_row = QHBoxLayout()
        center_row.setContentsMargins(0, 0, 0, 0)
        center_row.setSpacing(0)
        center_row.addItem(
            QSpacerItem(
                20,
                20,
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Minimum,
            )
        )

        self._card = QFrame()
        self._card.setObjectName("authCard")
        self._card.setFixedWidth(420)

        card_layout = QVBoxLayout(self._card)
        card_layout.setContentsMargins(28, 28, 28, 28)
        card_layout.setSpacing(14)

        self._title = QLabel(f"Welcome to {APP_NAME} 2.0")
        self._title.setObjectName("authTitle")
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self._title)

        self._subtitle = QLabel("Enter your name to continue.")
        self._subtitle.setObjectName("authSubtitle")
        self._subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self._subtitle)

        card_layout.addSpacing(8)

        self._name_label = QLabel("Your name")
        self._name_label.setObjectName("fieldLabel")
        card_layout.addWidget(self._name_label)

        self._name_input = QLineEdit()
        self._name_input.setObjectName("nameInput")
        self._name_input.setPlaceholderText("Type your name")
        self._name_input.setMaxLength(40)
        self._name_input.returnPressed.connect(self._submit)
        card_layout.addWidget(self._name_input)

        self._error_label = QLabel("")
        self._error_label.setObjectName("errorLabel")
        self._error_label.setWordWrap(True)
        self._error_label.hide()
        card_layout.addWidget(self._error_label)

        self._continue_button = QPushButton("Continue")
        self._continue_button.setObjectName("continueButton")
        self._continue_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._continue_button.setMinimumHeight(44)
        self._continue_button.clicked.connect(self._submit)
        card_layout.addWidget(self._continue_button)

        center_row.addWidget(self._card)
        center_row.addItem(
            QSpacerItem(
                20,
                20,
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Minimum,
            )
        )

        root.addLayout(center_row)
        root.addItem(
            QSpacerItem(
                20,
                20,
                QSizePolicy.Policy.Minimum,
                QSizePolicy.Policy.Expanding,
            )
        )

        self.setStyleSheet(
            f"""
            QWidget {{
                background-color: {C.BG};
                color: {C.TEXT};
            }}
            QFrame#authCard {{
                {CARD}
            }}
            QLabel#authTitle {{
                color: {C.ACCENT};
                font-size: 24px;
                font-weight: 700;
                background: transparent;
            }}
            QLabel#authSubtitle {{
                color: {C.MUTED};
                font-size: 13px;
                background: transparent;
            }}
            QLabel#fieldLabel {{
                color: {C.MUTED};
                font-size: 12px;
                font-weight: 600;
                background: transparent;
            }}
            QLineEdit#nameInput {{
                {INPUT}
            }}
            QLabel#errorLabel {{
                color: {C.DANGER};
                font-size: 12px;
                min-height: 16px;
                background: transparent;
            }}
            QPushButton#continueButton {{
                {PRIMARY_BTN}
            }}
            """
        )

    def _submit(self) -> None:
        user_name = self._name_input.text().strip()
        if not user_name:
            self._show_error("Please enter your name.")
            self._name_input.setFocus()
            return
        if len(user_name) < 2:
            self._show_error("Name must be at least 2 characters.")
            self._name_input.setFocus()
            return

        self._clear_error()
        user_id = user_name.lower().replace(" ", "_")
        self.login_completed.emit(user_name)
        self.login_successful.emit(user_id, user_name)

    def _show_error(self, message: str) -> None:
        self._error_label.setText(message)
        self._error_label.show()

    def _clear_error(self) -> None:
        self._error_label.clear()
        self._error_label.hide()

    def reset(self) -> None:
        self._name_input.clear()
        self._clear_error()
        self._continue_button.setEnabled(True)
        self._name_input.setFocus()