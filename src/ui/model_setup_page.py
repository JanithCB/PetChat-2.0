"""Model and mode selection page for PetChat-2.0."""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QSpacerItem,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.config import (
    CLOUD_PROVIDERS,
    DEFAULT_CLOUD_BASE_URL,
    DEFAULT_CLOUD_PROVIDER,
    DEFAULT_LOCAL_PROVIDER,
    ENABLE_CLOUD_MODELS,
    ENABLE_LOCAL_MODELS,
    LOCAL_PROVIDERS,
    MODE_GET_SUPPORT,
    MODE_HELP_SOMEONE,
)
from src.ui.styles import C


class ModelSetupPage(QWidget):
    chat_requested = pyqtSignal(str, str, dict)
    setup_confirmed = pyqtSignal(dict)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._user_name = ""
        self._build_ui()
        self._apply_styles()
        self.reset()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 28, 28, 28)
        root.setSpacing(0)
        root.addItem(
            QSpacerItem(
                20,
                20,
                QSizePolicy.Policy.Minimum,
                QSizePolicy.Policy.Expanding,
            )
        )

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        row.addItem(
            QSpacerItem(
                20,
                20,
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Minimum,
            )
        )

        self._card = QFrame()
        self._card.setObjectName("setupCard")
        self._card.setFixedWidth(520)
        card_layout = QVBoxLayout(self._card)
        card_layout.setContentsMargins(28, 28, 28, 28)
        card_layout.setSpacing(14)

        self._title = QLabel("Choose how to start")
        self._title.setObjectName("titleLabel")
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self._title)

        self._subtitle = QLabel("Select the mode and model for this session.")
        self._subtitle.setObjectName("subtitleLabel")
        self._subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self._subtitle)

        card_layout.addSpacing(6)

        self._mode_label = QLabel("Mode")
        self._mode_label.setObjectName("fieldLabel")
        card_layout.addWidget(self._mode_label)

        self._mode_combo = QComboBox()
        self._mode_combo.setObjectName("modeCombo")
        self._mode_combo.addItem("Get Support", MODE_GET_SUPPORT)
        self._mode_combo.addItem("Help Someone", MODE_HELP_SOMEONE)
        card_layout.addWidget(self._mode_combo)

        self._provider_label = QLabel("Provider")
        self._provider_label.setObjectName("fieldLabel")
        card_layout.addWidget(self._provider_label)

        provider_row = QHBoxLayout()
        provider_row.setSpacing(18)

        self._local_radio = QRadioButton("Local")
        self._local_radio.setObjectName("providerRadio")
        self._cloud_radio = QRadioButton("Cloud")
        self._cloud_radio.setObjectName("providerRadio")

        self._provider_group = QButtonGroup(self)
        self._provider_group.addButton(self._local_radio, 0)
        self._provider_group.addButton(self._cloud_radio, 1)

        provider_row.addWidget(self._local_radio)
        provider_row.addWidget(self._cloud_radio)
        provider_row.addStretch(1)
        card_layout.addLayout(provider_row)

        self._provider_group.buttonToggled.connect(self._on_provider_toggled)

        self._provider_stack = QStackedWidget()
        self._provider_stack.addWidget(self._build_local_panel())
        self._provider_stack.addWidget(self._build_cloud_panel())
        card_layout.addWidget(self._provider_stack)

        self._status_label = QLabel("")
        self._status_label.setObjectName("statusLabel")
        self._status_label.setWordWrap(True)
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.hide()
        card_layout.addWidget(self._status_label)

        self._start_button = QPushButton("Start Chat")
        self._start_button.setObjectName("startButton")
        self._start_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._start_button.setMinimumHeight(46)
        self._start_button.clicked.connect(self._on_start)
        card_layout.addWidget(self._start_button)

        row.addWidget(self._card)
        row.addItem(
            QSpacerItem(
                20,
                20,
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Minimum,
            )
        )

        root.addLayout(row)
        root.addItem(
            QSpacerItem(
                20,
                20,
                QSizePolicy.Policy.Minimum,
                QSizePolicy.Policy.Expanding,
            )
        )

    def _build_local_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        label = QLabel("Local model")
        label.setObjectName("fieldLabel")
        layout.addWidget(label)

        self._local_model_combo = QComboBox()
        self._local_model_combo.setObjectName("panelCombo")
        for provider_id, model_id in LOCAL_PROVIDERS.items():
            self._local_model_combo.addItem(model_id, provider_id)
        default_index = self._local_model_combo.findData(DEFAULT_LOCAL_PROVIDER)
        if default_index >= 0:
            self._local_model_combo.setCurrentIndex(default_index)
        layout.addWidget(self._local_model_combo)

        note = QLabel("Uses your local Ollama server.")
        note.setObjectName("noteLabel")
        note.setWordWrap(True)
        layout.addWidget(note)

        return panel

    def _build_cloud_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        model_label = QLabel("Cloud model")
        model_label.setObjectName("fieldLabel")
        layout.addWidget(model_label)

        self._cloud_model_input = QLineEdit()
        self._cloud_model_input.setObjectName("panelInput")
        self._cloud_model_input.setPlaceholderText("meta-llama/llama-4-scout-17b-16e-instruct")
        self._cloud_model_input.setText(CLOUD_PROVIDERS.get(DEFAULT_CLOUD_PROVIDER, ""))
        layout.addWidget(self._cloud_model_input)

        base_label = QLabel("API base URL")
        base_label.setObjectName("fieldLabel")
        layout.addWidget(base_label)

        self._cloud_base_url_input = QLineEdit()
        self._cloud_base_url_input.setObjectName("panelInput")
        self._cloud_base_url_input.setPlaceholderText("https://api.openai.com/v1")
        self._cloud_base_url_input.setText(DEFAULT_CLOUD_BASE_URL)
        layout.addWidget(self._cloud_base_url_input)

        key_label = QLabel("API key")
        key_label.setObjectName("fieldLabel")
        layout.addWidget(key_label)

        self._cloud_api_key_input = QLineEdit()
        self._cloud_api_key_input.setObjectName("panelInput")
        self._cloud_api_key_input.setPlaceholderText("Paste your API key")
        self._cloud_api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self._cloud_api_key_input)

        note = QLabel("Use any OpenAI-compatible chat endpoint.")
        note.setObjectName("noteLabel")
        note.setWordWrap(True)
        layout.addWidget(note)

        return panel

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            f"""
            QWidget {{
                background-color: {C.BG};
                color: {C.TEXT};
            }}
            QFrame#setupCard {{
                background-color: {C.SURFACE};
                border: 1px solid {C.DIVIDER};
                border-radius: 16px;
            }}
            QLabel#titleLabel {{
                color: {C.ACCENT};
                font-size: 22px;
                font-weight: 700;
                background: transparent;
            }}
            QLabel#subtitleLabel {{
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
            QLabel#noteLabel {{
                color: {C.STATUS_TEXT};
                font-size: 12px;
                background: transparent;
            }}
            QLabel#statusLabel {{
                color: {C.STATUS_TEXT};
                font-size: 12px;
                background: transparent;
                min-height: 18px;
            }}
            QComboBox#modeCombo, QComboBox#panelCombo {{
                background-color: {C.INPUT_BG};
                color: {C.INPUT_TEXT};
                border: 1px solid {C.DIVIDER};
                border-radius: 12px;
                padding: 10px 12px;
                min-height: 18px;
            }}
            QComboBox#modeCombo:hover, QComboBox#panelCombo:hover {{
                border: 1px solid {C.ACCENT};
            }}
            QComboBox#modeCombo::drop-down, QComboBox#panelCombo::drop-down {{
                border: none;
                width: 24px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {C.SURFACE_ALT};
                color: {C.TEXT};
                border: 1px solid {C.DIVIDER};
                selection-background-color: {C.ACCENT};
                selection-color: {C.USER_TEXT};
            }}
            QLineEdit#panelInput {{
                background-color: {C.INPUT_BG};
                color: {C.INPUT_TEXT};
                border: 1px solid {C.DIVIDER};
                border-radius: 12px;
                padding: 10px 12px;
            }}
            QLineEdit#panelInput:focus {{
                border: 1px solid {C.ACCENT};
            }}
            QRadioButton#providerRadio {{
                color: {C.TEXT};
                spacing: 8px;
                font-size: 13px;
            }}
            QRadioButton#providerRadio::indicator {{
                width: 16px;
                height: 16px;
                border-radius: 8px;
                border: 1px solid {C.DIVIDER};
                background: {C.SURFACE_ALT};
            }}
            QRadioButton#providerRadio::indicator:checked {{
                background: {C.ACCENT};
                border: 1px solid {C.ACCENT};
            }}
            QPushButton#startButton {{
                background-color: {C.ACCENT};
                color: {C.USER_TEXT};
                border: none;
                border-radius: 12px;
                padding: 10px 16px;
                font-size: 14px;
                font-weight: 700;
            }}
            QPushButton#startButton:hover {{
                background-color: {C.ACCENT_HOVER};
            }}
            QPushButton#startButton:disabled {{
                background-color: #3A3A3A;
                color: #808080;
            }}
            """
        )

    def _on_provider_toggled(self, button: QRadioButton, checked: bool) -> None:
        if not checked:
            return
        if button is self._local_radio:
            self._provider_stack.setCurrentIndex(0)
        else:
            self._provider_stack.setCurrentIndex(1)
        self._clear_status()

    def _on_start(self) -> None:
        user_name = self._user_name.strip()
        if not user_name:
            self._show_status("Please go back and enter your name first.", error=True)
            return

        mode = str(self._mode_combo.currentData())
        session_config = self._build_session_config()
        if session_config is None:
            return

        payload = dict(session_config)
        payload["user_name"] = user_name
        payload["mode"] = mode

        self._start_button.setEnabled(False)
        self.chat_requested.emit(user_name, mode, session_config)
        self.setup_confirmed.emit(payload)
        self._start_button.setEnabled(True)

    def _build_session_config(self) -> dict[str, Any] | None:
        if self._local_radio.isChecked():
            provider_id = str(self._local_model_combo.currentData() or "")
            model_id = str(self._local_model_combo.currentText()).strip()
            if not provider_id or not model_id:
                self._show_status("Please select a local model.", error=True)
                return None
            self._clear_status()
            return {
                "provider_type": "local",
                "provider_id": provider_id,
                "model_id": model_id,
                "base_url": "",
                "api_key": "",
                "is_local": True,
            }

        model_id = self._cloud_model_input.text().strip()
        base_url = self._cloud_base_url_input.text().strip().rstrip("/")
        api_key = self._cloud_api_key_input.text().strip()
        if not model_id:
            self._show_status("Please enter a cloud model id.", error=True)
            self._cloud_model_input.setFocus()
            return None
        if not base_url:
            self._show_status("Please enter the API base URL.", error=True)
            self._cloud_base_url_input.setFocus()
            return None
        if not api_key:
            self._show_status("Please enter the API key.", error=True)
            self._cloud_api_key_input.setFocus()
            return None

        self._clear_status()
        return {
            "provider_type": "cloud",
            "provider_id": "custom_api",
            "model_id": model_id,
            "base_url": base_url,
            "api_key": api_key,
            "is_local": False,
        }

    def _show_status(self, message: str, error: bool = False) -> None:
        color = C.DANGER if error else C.STATUS_TEXT
        self._status_label.setStyleSheet(
            f"color: {color}; font-size: 12px; background: transparent;"
        )
        self._status_label.setText(message)
        self._status_label.show()

    def _clear_status(self) -> None:
        self._status_label.clear()
        self._status_label.hide()

    def set_user_name(self, user_name: str) -> None:
        self._user_name = user_name.strip()
        if self._user_name:
            self._title.setText(f"Hello {self._user_name}")
            self._subtitle.setText("Choose a mode and model for this chat.")
        else:
            self._title.setText("Choose how to start")
            self._subtitle.setText("Select the mode and model for this session.")
        self._clear_status()

    def set_user(self, user_id: str, user_name: str) -> None:
        _ = user_id
        self.set_user_name(user_name)

    def reset(self) -> None:
        self._user_name = ""
        self._mode_combo.setCurrentIndex(0)

        self._local_radio.setEnabled(ENABLE_LOCAL_MODELS)
        self._cloud_radio.setEnabled(ENABLE_CLOUD_MODELS)

        if ENABLE_LOCAL_MODELS:
            self._local_radio.setChecked(True)
            self._provider_stack.setCurrentIndex(0)
        elif ENABLE_CLOUD_MODELS:
            self._cloud_radio.setChecked(True)
            self._provider_stack.setCurrentIndex(1)

        local_index = self._local_model_combo.findData(DEFAULT_LOCAL_PROVIDER)
        if local_index >= 0:
            self._local_model_combo.setCurrentIndex(local_index)

        self._cloud_model_input.setText(CLOUD_PROVIDERS.get(DEFAULT_CLOUD_PROVIDER, ""))
        self._cloud_base_url_input.setText(DEFAULT_CLOUD_BASE_URL)
        self._cloud_api_key_input.clear()
        self._start_button.setEnabled(True)
        self._clear_status()
        self.set_user_name("")