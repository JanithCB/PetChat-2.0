"""Simple name-entry auth page for PetChat-2.0."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QMovie
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
from src.ui.styles import C


CHARACTER_IMAGE_NAME = "auth_anime.gif"


class AuthPage(QWidget):
    login_completed = pyqtSignal(str)
    login_successful = pyqtSignal(str, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._character_movie: QMovie | None = None
        self._build_ui()
        self.reset()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 32)
        root.setSpacing(0)

        root.addItem(
            QSpacerItem(
                20,
                24,
                QSizePolicy.Policy.Minimum,
                QSizePolicy.Policy.Expanding,
            )
        )

        self._brand_title = QLabel(APP_NAME)
        self._brand_title.setObjectName("brandTitle")
        self._brand_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self._brand_title)

        self._brand_caption = QLabel("A warm little place to start chatting.")
        self._brand_caption.setObjectName("brandCaption")
        self._brand_caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self._brand_caption)

        root.addSpacing(26)

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
        self._card.setMaximumWidth(500)
        self._card.setMinimumWidth(320)
        self._card.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Maximum,
        )

        card_layout = QVBoxLayout(self._card)
        card_layout.setContentsMargins(38, 34, 38, 34)
        card_layout.setSpacing(16)

        self._character_image = QLabel()
        self._character_image.setObjectName("authCharacterImage")
        self._character_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._character_image.setMinimumHeight(170)
        self._character_image.setMaximumHeight(190)
        self._character_image.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        card_layout.addWidget(self._character_image)

        self._subtitle = QLabel("Welcome back. Enter your name to continue.")
        self._subtitle.setObjectName("authSubtitle")
        self._subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._subtitle.setWordWrap(True)
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
        self._continue_button.setMinimumHeight(46)
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
                40,
                QSizePolicy.Policy.Minimum,
                QSizePolicy.Policy.Expanding,
            )
        )

        self._load_character_gif()

        self.setStyleSheet(
            f"""
            QWidget {{
                background-color: {C.BG};
                color: {C.TEXT};
            }}

            QLabel#brandTitle {{
                color: {C.ACCENT};
                font-size: 56px;
                font-weight: 900;
                letter-spacing: 1px;
                background: transparent;
            }}

            QLabel#brandCaption {{
                color: {C.MUTED};
                font-size: 14px;
                font-weight: 500;
                background: transparent;
                margin-top: 4px;
            }}

            QFrame#authCard {{
                background-color: #050505;
                border: 1.5px solid {C.ACCENT};
                border-radius: 24px;
            }}

            QLabel#authCharacterImage {{
                background: transparent;
            }}

            QLabel#authSubtitle {{
                color: {C.MUTED};
                font-size: 14px;
                font-weight: 500;
                background: transparent;
            }}

            QLabel#fieldLabel {{
                color: {C.MUTED};
                font-size: 12px;
                font-weight: 700;
                background: transparent;
            }}

            QLineEdit#nameInput {{
                background-color: {C.INPUT_BG};
                color: {C.INPUT_TEXT};
                border: 2px solid {C.ACCENT};
                border-radius: 14px;
                padding: 12px 14px;
                font-size: 14px;
            }}

            QLineEdit#nameInput:focus {{
                border: 2px solid {C.ACCENT_HOVER};
            }}

            QLabel#errorLabel {{
                color: {C.DANGER};
                font-size: 12px;
                min-height: 16px;
                background: transparent;
            }}

            QPushButton#continueButton {{
                background-color: {C.ACCENT};
                color: {C.USER_TEXT};
                border: none;
                border-radius: 14px;
                padding: 12px;
                font-size: 15px;
                font-weight: 800;
            }}

            QPushButton#continueButton:hover {{
                background-color: {C.ACCENT_HOVER};
            }}

            QPushButton#continueButton:pressed {{
                background-color: {C.ACCENT_HOVER};
            }}
            """
        )

    def _find_asset_path(self, filename: str) -> Path | None:
        current_file = Path(__file__).resolve()

        for parent in [current_file.parent, *current_file.parents]:
            possible_paths = [
                parent / "assets" / filename,
                parent / "images" / filename,
                parent / "resources" / filename,
                parent / filename,
            ]

            for path in possible_paths:
                if path.exists():
                    return path

        return None

    def _load_character_gif(self) -> None:
        gif_path = self._find_asset_path(CHARACTER_IMAGE_NAME)

        if gif_path is None:
            self._character_image.setText("GIF not found")
            self._character_image.setStyleSheet(
                f"color: {C.MUTED}; background: transparent;"
            )
            return

        self._character_movie = QMovie(str(gif_path))

        if not self._character_movie.isValid():
            self._character_image.setText("Invalid GIF")
            self._character_image.setStyleSheet(
                f"color: {C.MUTED}; background: transparent;"
            )
            return

        self._refresh_character_gif()
        self._character_image.setMovie(self._character_movie)
        self._character_movie.start()

    def _refresh_character_gif(self) -> None:
        if self._character_movie is None:
            return

        self._character_movie.setScaledSize(QSize(230, 170))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._refresh_character_gif()

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