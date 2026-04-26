"""Model and mode selection page for PetChat-2.0.

Redesigned desktop layout:
- wider two-column setup panel
- readable color hierarchy
- no overlapping text
- consistent card spacing
- scroll-safe content for small screens
"""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
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


SETUP_MAX_WIDTH = 1040


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
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setObjectName("setupScroll")
        root.addWidget(self._scroll)

        page = QWidget()
        page.setObjectName("setupPage")
        self._scroll.setWidget(page)

        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(32, 32, 32, 32)
        page_layout.setSpacing(0)
        page_layout.addStretch(1)

        center_row = QHBoxLayout()
        center_row.setContentsMargins(0, 0, 0, 0)
        center_row.setSpacing(0)
        center_row.addStretch(1)

        self._card = QFrame()
        self._card.setObjectName("setupCard")
        self._card.setMaximumWidth(SETUP_MAX_WIDTH)
        self._card.setMinimumWidth(760)
        apply_card_shadow(self._card, blur_radius=36.0, y_offset=8.0)
        center_row.addWidget(self._card)

        center_row.addStretch(1)
        page_layout.addLayout(center_row)
        page_layout.addStretch(1)

        card_layout = QVBoxLayout(self._card)
        card_layout.setContentsMargins(34, 30, 34, 30)
        card_layout.setSpacing(24)

        header = QFrame()
        header.setObjectName("heroHeader")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)

        self._title = QLabel("Choose how to start")
        self._title.setObjectName("titleLabel")
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title.setWordWrap(True)
        header_layout.addWidget(self._title)

        self._subtitle = QLabel("Select a conversation mode and model for this session.")
        self._subtitle.setObjectName("subtitleLabel")
        self._subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._subtitle.setWordWrap(True)
        header_layout.addWidget(self._subtitle)
        card_layout.addWidget(header)

        main_grid = QHBoxLayout()
        main_grid.setContentsMargins(0, 0, 0, 0)
        main_grid.setSpacing(18)

        left_column = QVBoxLayout()
        left_column.setContentsMargins(0, 0, 0, 0)
        left_column.setSpacing(18)
        left_column.addWidget(self._build_mode_section())
        left_column.addWidget(self._build_provider_section())
        left_column.addStretch(1)

        right_column = QVBoxLayout()
        right_column.setContentsMargins(0, 0, 0, 0)
        right_column.setSpacing(18)

        self._provider_stack = QStackedWidget()
        self._provider_stack.setObjectName("providerStack")
        self._provider_stack.addWidget(self._build_local_panel())
        self._provider_stack.addWidget(self._build_cloud_panel())
        right_column.addWidget(self._provider_stack)
        right_column.addStretch(1)

        main_grid.addLayout(left_column, 1)
        main_grid.addLayout(right_column, 1)
        card_layout.addLayout(main_grid)

        self._status_label = QLabel("")
        self._status_label.setObjectName("statusLabel")
        self._status_label.setWordWrap(True)
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.hide()
        card_layout.addWidget(self._status_label)

        self._start_button = QPushButton("Start Chat")
        self._start_button.setObjectName("startButton")
        self._start_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._start_button.setMinimumHeight(54)
        self._start_button.clicked.connect(self._on_start)
        card_layout.addWidget(self._start_button)

    def _build_mode_section(self) -> QWidget:
        section = self._make_section("Conversation mode", "Choose how PetChat should respond during this session.")
        layout = section.layout()

        support_button = self._make_choice_button("Get Support", "Talk about how you feel", checked=True)
        help_button = self._make_choice_button("Help Someone", "Get coaching to support another person")

        self._mode_buttons = {MODE_GET_SUPPORT: support_button, MODE_HELP_SOMEONE: help_button}
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
        section = self._make_section("Model source", "Choose local privacy or a cloud endpoint.")
        layout = section.layout()

        local_button = self._make_choice_button("Local", "Private Ollama model on this computer", checked=True)
        cloud_button = self._make_choice_button("Cloud", "Use a custom API endpoint")

        self._provider_buttons = {"local": local_button, "cloud": cloud_button}
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
        panel = self._make_section("Local model", "Choose the Ollama model PetChat should use.")
        layout = panel.layout()

        self._local_model_buttons.clear()
        for provider_id, model_id in LOCAL_PROVIDERS.items():
            button = self._make_choice_button(
                str(model_id),
                f"Provider: {provider_id}",
                checked=provider_id == DEFAULT_LOCAL_PROVIDER,
            )
            button.clicked.connect(lambda checked=False, pid=provider_id: self._select_local_model(pid))
            self._local_model_buttons[provider_id] = button
            layout.addWidget(button)

        return panel

    def _build_cloud_panel(self) -> QWidget:
        panel = self._make_section(
            "Cloud settings",
            "Use an OpenAI-compatible endpoint. Your key is only used for this session.",
        )
        layout = panel.layout()

        layout.addWidget(self._make_input_label("Model ID"))
        self._cloud_model_input = QLineEdit()
        self._cloud_model_input.setObjectName("panelInput")
        self._cloud_model_input.setPlaceholderText("meta-llama/llama-4-scout-17b-16e-instruct")
        self._cloud_model_input.setText(CLOUD_PROVIDERS.get(DEFAULT_CLOUD_PROVIDER, ""))
        layout.addWidget(self._cloud_model_input)

        layout.addWidget(self._make_input_label("API base URL"))
        self._cloud_base_url_input = QLineEdit()
        self._cloud_base_url_input.setObjectName("panelInput")
        self._cloud_base_url_input.setPlaceholderText("https://api.openai.com/v1")
        self._cloud_base_url_input.setText(DEFAULT_CLOUD_BASE_URL)
        layout.addWidget(self._cloud_base_url_input)

        layout.addWidget(self._make_input_label("API key"))
        self._cloud_api_key_input = QLineEdit()
        self._cloud_api_key_input.setObjectName("panelInput")
        self._cloud_api_key_input.setPlaceholderText("Paste your API key")
        self._cloud_api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self._cloud_api_key_input)
        layout.addStretch(1)

        return panel

    def _make_section(self, title: str, note: str) -> QFrame:
        section = QFrame()
        section.setObjectName("sectionCard")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(22, 20, 22, 22)
        layout.setSpacing(12)

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

    def _make_choice_button(self, title: str, description: str, checked: bool = False) -> QPushButton:
        button = QPushButton(f"{title}\n{description}")
        button.setObjectName("choiceButton")
        button.setCheckable(True)
        button.setChecked(checked)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setMinimumHeight(82)
        button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        return button

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            f"""
            QWidget#setupPage, QScrollArea#setupScroll {{
                background-color: {C.BG};
                color: {C.TEXT};
                border: none;
            }}

            QFrame#setupCard {{
                background-color: #111111;
                border: 1px solid #2B2B2B;
                border-radius: 24px;
            }}

            QFrame#heroHeader {{
                background-color: transparent;
                border: none;
            }}

            QFrame#sectionCard {{
                background-color: #171717;
                border: 1px solid #2A2A2A;
                border-radius: 20px;
            }}

            QLabel#titleLabel {{
                color: #F4F4F5;
                font-size: 28px;
                font-weight: 850;
                letter-spacing: -0.4px;
                background: transparent;
            }}

            QLabel#subtitleLabel {{
                color: #A1A1AA;
                font-size: 14px;
                font-weight: 450;
                background: transparent;
            }}

            QLabel#fieldLabel {{
                color: #F4F4F5;
                font-size: 15px;
                font-weight: 800;
                background: transparent;
            }}

            QLabel#noteLabel {{
                color: #A1A1AA;
                font-size: 13px;
                font-weight: 450;
                background: transparent;
                line-height: 145%;
            }}

            QLabel#inputLabel {{
                color: #D4D4D8;
                font-size: 12px;
                font-weight: 700;
                background: transparent;
                margin-top: 4px;
            }}

            QLabel#statusLabel {{
                color: #A1A1AA;
                font-size: 13px;
                background: transparent;
                min-height: 20px;
            }}

            QPushButton#choiceButton {{
                background-color: #101010;
                color: #F4F4F5;
                border: 1px solid #303030;
                border-radius: 16px;
                padding: 14px 18px;
                text-align: left;
                font-size: 14px;
                font-weight: 650;
                line-height: 150%;
            }}

            QPushButton#choiceButton:hover {{
                background-color: #1E1E1E;
                border: 1px solid #565656;
                color: #FFFFFF;
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
                border-radius: 14px;
                padding: 12px 14px;
                font-size: 13px;
                min-height: 22px;
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
                border-radius: 16px;
                padding: 13px 22px;
                font-size: 15px;
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
        self._status_label.setStyleSheet(f"color: {color}; font-size: 13px; background: transparent;")
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
