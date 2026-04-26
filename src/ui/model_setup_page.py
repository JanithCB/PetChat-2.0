"""Compact model and mode selection page for PetChat-2.0."""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
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
from src.ui.styles import C, apply_card_shadow


SETUP_MAX_WIDTH = 820
SETUP_MIN_WIDTH = 680


class ModelSetupPage(QWidget):
    chat_requested = pyqtSignal(str, str, dict)
    setup_confirmed = pyqtSignal(dict)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._user_name = ""
        self._selected_mode = MODE_GET_SUPPORT
        self._selected_provider = "local"
        self._selected_local_provider = DEFAULT_LOCAL_PROVIDER

        self._mode_buttons: dict[str, QPushButton] = {}
        self._provider_buttons: dict[str, QPushButton] = {}
        self._local_model_buttons: dict[str, QPushButton] = {}

        self._build_ui()
        self._apply_styles()
        self.reset()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(0)
        root.addStretch(1)

        center = QHBoxLayout()
        center.addStretch(1)

        self._card = QFrame()
        self._card.setObjectName("setupCard")
        self._card.setMaximumWidth(SETUP_MAX_WIDTH)
        self._card.setMinimumWidth(SETUP_MIN_WIDTH)
        apply_card_shadow(self._card, blur_radius=30.0, y_offset=7.0)

        center.addWidget(self._card)
        center.addStretch(1)

        root.addLayout(center)
        root.addStretch(1)

        card_layout = QVBoxLayout(self._card)
        card_layout.setContentsMargins(26, 22, 26, 22)
        card_layout.setSpacing(14)

        self._title = QLabel("Choose how to start")
        self._title.setObjectName("titleLabel")
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self._title)

        self._subtitle = QLabel("Select your support mode and model.")
        self._subtitle.setObjectName("subtitleLabel")
        self._subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self._subtitle)

        grid = QGridLayout()
        grid.setContentsMargins(0, 8, 0, 0)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(14)

        grid.addWidget(self._build_mode_section(), 0, 0)
        grid.addWidget(self._build_provider_section(), 0, 1)

        self._provider_stack = QStackedWidget()
        self._provider_stack.setObjectName("providerStack")
        self._provider_stack.addWidget(self._build_local_panel())
        self._provider_stack.addWidget(self._build_cloud_panel())
        grid.addWidget(self._provider_stack, 1, 0, 1, 2)

        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        card_layout.addLayout(grid)

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

    def _build_mode_section(self) -> QWidget:
        section = self._make_section(
            "Conversation mode",
            "How should PetChat respond?",
        )
        layout = section.layout()

        support_button = self._make_choice_button(
            "Get Support",
            "Talk about how you feel",
            checked=True,
        )
        help_button = self._make_choice_button(
            "Help Someone",
            "Coach me to support someone",
        )

        self._mode_buttons = {
            MODE_GET_SUPPORT: support_button,
            MODE_HELP_SOMEONE: help_button,
        }

        self._mode_group = QButtonGroup(self)
        self._mode_group.setExclusive(True)
        self._mode_group.addButton(support_button)
        self._mode_group.addButton(help_button)

        support_button.clicked.connect(lambda: self._select_mode(MODE_GET_SUPPORT))
        help_button.clicked.connect(lambda: self._select_mode(MODE_HELP_SOMEONE))

        layout.addWidget(support_button)
        layout.addWidget(help_button)
        return section

    def _build_provider_section(self) -> QWidget:
        section = self._make_section(
            "Model source",
            "Choose local or cloud.",
        )
        layout = section.layout()

        local_button = self._make_choice_button(
            "Local",
            "Private Ollama model",
            checked=True,
        )
        cloud_button = self._make_choice_button(
            "Cloud",
            "Custom API endpoint",
        )

        self._provider_buttons = {
            "local": local_button,
            "cloud": cloud_button,
        }

        self._provider_group = QButtonGroup(self)
        self._provider_group.setExclusive(True)
        self._provider_group.addButton(local_button)
        self._provider_group.addButton(cloud_button)

        local_button.clicked.connect(lambda: self._select_provider("local"))
        cloud_button.clicked.connect(lambda: self._select_provider("cloud"))

        layout.addWidget(local_button)
        layout.addWidget(cloud_button)
        return section

    def _build_local_panel(self) -> QWidget:
        panel = self._make_section(
            "Local model",
            "Choose the Ollama model PetChat should use.",
        )
        layout = panel.layout()

        self._local_model_buttons.clear()

        model_grid = QGridLayout()
        model_grid.setContentsMargins(0, 0, 0, 0)
        model_grid.setHorizontalSpacing(10)
        model_grid.setVerticalSpacing(10)

        for index, (provider_id, model_id) in enumerate(LOCAL_PROVIDERS.items()):
            button = self._make_choice_button(
                str(model_id),
                f"Provider: {provider_id}",
                checked=provider_id == DEFAULT_LOCAL_PROVIDER,
            )
            button.clicked.connect(
                lambda checked=False, pid=provider_id: self._select_local_model(pid)
            )
            self._local_model_buttons[provider_id] = button
            model_grid.addWidget(button, index // 2, index % 2)

        layout.addLayout(model_grid)
        return panel

    def _build_cloud_panel(self) -> QWidget:
        panel = self._make_section(
            "Cloud settings",
            "Use an OpenAI-compatible endpoint.",
        )
        layout = panel.layout()

        form_grid = QGridLayout()
        form_grid.setContentsMargins(0, 0, 0, 0)
        form_grid.setHorizontalSpacing(10)
        form_grid.setVerticalSpacing(8)

        self._cloud_model_input = QLineEdit()
        self._cloud_model_input.setObjectName("panelInput")
        self._cloud_model_input.setPlaceholderText("Model ID")
        self._cloud_model_input.setText(CLOUD_PROVIDERS.get(DEFAULT_CLOUD_PROVIDER, ""))

        self._cloud_base_url_input = QLineEdit()
        self._cloud_base_url_input.setObjectName("panelInput")
        self._cloud_base_url_input.setPlaceholderText("API base URL")
        self._cloud_base_url_input.setText(DEFAULT_CLOUD_BASE_URL)

        self._cloud_api_key_input = QLineEdit()
        self._cloud_api_key_input.setObjectName("panelInput")
        self._cloud_api_key_input.setPlaceholderText("API key")
        self._cloud_api_key_input.setEchoMode(QLineEdit.EchoMode.Password)

        form_grid.addWidget(self._make_input_label("Model ID"), 0, 0)
        form_grid.addWidget(self._make_input_label("API base URL"), 0, 1)
        form_grid.addWidget(self._cloud_model_input, 1, 0)
        form_grid.addWidget(self._cloud_base_url_input, 1, 1)
        form_grid.addWidget(self._make_input_label("API key"), 2, 0, 1, 2)
        form_grid.addWidget(self._cloud_api_key_input, 3, 0, 1, 2)

        layout.addLayout(form_grid)
        return panel

    def _make_section(self, title: str, note: str) -> QFrame:
        section = QFrame()
        section.setObjectName("sectionCard")

        layout = QVBoxLayout(section)
        layout.setContentsMargins(18, 15, 18, 16)
        layout.setSpacing(8)

        label = QLabel(title)
        label.setObjectName("fieldLabel")
        layout.addWidget(label)

        helper = QLabel(note)
        helper.setObjectName("noteLabel")
        helper.setWordWrap(True)
        layout.addWidget(helper)

        return section

    def _make_input_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("inputLabel")
        return label

    def _make_choice_button(
        self,
        title: str,
        description: str,
        checked: bool = False,
    ) -> QPushButton:
        button = QPushButton(f"{title}\n{description}")
        button.setObjectName("choiceButton")
        button.setCheckable(True)
        button.setChecked(checked)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setMinimumHeight(58)
        button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        return button

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            f"""
            QWidget {{
                background-color: {C.BG};
                color: {C.TEXT};
            }}

            QFrame#setupCard {{
                background-color: #111111;
                border: 1px solid #2B2B2B;
                border-radius: 22px;
            }}

            QFrame#sectionCard {{
                background-color: #171717;
                border: 1px solid #2A2A2A;
                border-radius: 17px;
            }}

            QLabel#titleLabel {{
                color: #F4F4F5;
                font-size: 25px;
                font-weight: 850;
                background: transparent;
            }}

            QLabel#subtitleLabel {{
                color: #A1A1AA;
                font-size: 13px;
                background: transparent;
            }}

            QLabel#fieldLabel {{
                color: #F4F4F5;
                font-size: 14px;
                font-weight: 800;
                background: transparent;
            }}

            QLabel#noteLabel {{
                color: #A1A1AA;
                font-size: 12px;
                background: transparent;
            }}

            QLabel#inputLabel {{
                color: #D4D4D8;
                font-size: 11px;
                font-weight: 700;
                background: transparent;
            }}

            QLabel#statusLabel {{
                color: #A1A1AA;
                font-size: 12px;
                background: transparent;
                min-height: 18px;
            }}

            QPushButton#choiceButton {{
                background-color: #101010;
                color: #F4F4F5;
                border: 1px solid #303030;
                border-radius: 14px;
                padding: 9px 14px;
                text-align: left;
                font-size: 13px;
                font-weight: 650;
            }}

            QPushButton#choiceButton:hover {{
                background-color: #1E1E1E;
                border: 1px solid #565656;
            }}

            QPushButton#choiceButton:checked {{
                background-color: #241F12;
                color: #FFD84D;
                border: 1px solid #FFD84D;
                font-weight: 800;
            }}

            QPushButton#choiceButton:disabled {{
                background-color: #121212;
                color: #666666;
                border: 1px solid #262626;
            }}

            QLineEdit#panelInput {{
                background-color: #101010;
                color: #F4F4F5;
                border: 1px solid #303030;
                border-radius: 12px;
                padding: 9px 12px;
                font-size: 12px;
                min-height: 20px;
                selection-background-color: #FFD84D;
                selection-color: #111111;
            }}

            QLineEdit#panelInput:hover {{
                border: 1px solid #565656;
            }}

            QLineEdit#panelInput:focus {{
                border: 1px solid #FFD84D;
                background-color: #141414;
            }}

            QPushButton#startButton {{
                background-color: #FFD84D;
                color: #111111;
                border: 1px solid #FFD84D;
                border-radius: 14px;
                padding: 10px 18px;
                font-size: 14px;
                font-weight: 850;
            }}

            QPushButton#startButton:hover {{
                background-color: #FFE27A;
                border: 1px solid #FFE27A;
            }}

            QPushButton#startButton:pressed {{
                background-color: #E6BE2E;
                border: 1px solid #E6BE2E;
            }}

            QPushButton#startButton:disabled {{
                background-color: #2A2A2A;
                color: #777777;
                border: 1px solid #333333;
            }}
            """
        )

    def _select_mode(self, mode: str) -> None:
        self._selected_mode = mode
        for mode_id, button in self._mode_buttons.items():
            button.setChecked(mode_id == mode)
        self._clear_status()

    def _select_provider(self, provider: str) -> None:
        self._selected_provider = provider
        for provider_id, button in self._provider_buttons.items():
            button.setChecked(provider_id == provider)
        self._provider_stack.setCurrentIndex(0 if provider == "local" else 1)
        self._clear_status()

    def _select_local_model(self, provider_id: str) -> None:
        self._selected_local_provider = provider_id
        for item_provider_id, button in self._local_model_buttons.items():
            button.setChecked(item_provider_id == provider_id)
        self._clear_status()

    def _on_start(self) -> None:
        user_name = self._user_name.strip()
        if not user_name:
            self._show_status("Please go back and enter your name first.", error=True)
            return

        mode = self._selected_mode
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
        if self._selected_provider == "local":
            provider_id = self._selected_local_provider
            model_id = str(LOCAL_PROVIDERS.get(provider_id, "")).strip()
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
        color = C.DANGER if error else "#A1A1AA"
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
            self._title.setText(f"Welcome, {self._user_name}")
            self._subtitle.setText("Set your support mode and choose the model PetChat should use.")
        else:
            self._title.setText("Choose how to start")
            self._subtitle.setText("Select a conversation mode and model for this session.")
        self._clear_status()

    def set_user(self, user_id: str, user_name: str) -> None:
        _ = user_id
        self.set_user_name(user_name)

    def reset(self) -> None:
        self._user_name = ""
        self._select_mode(MODE_GET_SUPPORT)

        for button in self._provider_buttons.values():
            button.setEnabled(True)

        if "local" in self._provider_buttons:
            self._provider_buttons["local"].setEnabled(ENABLE_LOCAL_MODELS)

        if "cloud" in self._provider_buttons:
            self._provider_buttons["cloud"].setEnabled(ENABLE_CLOUD_MODELS)

        if ENABLE_LOCAL_MODELS:
            self._select_provider("local")
        elif ENABLE_CLOUD_MODELS:
            self._select_provider("cloud")
        else:
            self._select_provider("local")
            self._start_button.setEnabled(False)

        self._selected_local_provider = DEFAULT_LOCAL_PROVIDER
        if self._selected_local_provider not in LOCAL_PROVIDERS and LOCAL_PROVIDERS:
            self._selected_local_provider = next(iter(LOCAL_PROVIDERS.keys()))

        self._select_local_model(self._selected_local_provider)

        self._cloud_model_input.setText(CLOUD_PROVIDERS.get(DEFAULT_CLOUD_PROVIDER, ""))
        self._cloud_base_url_input.setText(DEFAULT_CLOUD_BASE_URL)
        self._cloud_api_key_input.clear()

        self._start_button.setEnabled(ENABLE_LOCAL_MODELS or ENABLE_CLOUD_MODELS)
        self._clear_status()
        self.set_user_name("")