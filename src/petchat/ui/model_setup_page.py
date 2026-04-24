"""
ui/model_setup_page.py — Model / provider selection page for PetChat-2.0.

Flow
----
AuthPage  →  ModelSetupPage  →  ChatPage

The user picks Cloud AI or Local AI, selects a model, supplies any required
API key, then clicks "Start chatting".

Signals
-------
setup_confirmed(session_config: dict)
    Emitted when validation passes.  The dict always contains:
        provider_type : "cloud" | "local"
        provider_id   : str   (stable key from config.py)
        model_id      : str   (full model string)
        is_local      : bool
        api_key       : str   (empty string for local)
        user_id       : str   (injected by set_user)
        username      : str   (injected by set_user)
"""

from __future__ import annotations

import os
from typing import Any

from PyQt6.QtCore import QSize, Qt, QThread, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QSpacerItem,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from petchat.config import (
    CLOUD_PROVIDERS,
    DEFAULT_CLOUD_PROVIDER,
    DEFAULT_LOCAL_PROVIDER,
    ENABLE_CLOUD_MODELS,
    ENABLE_LOCAL_MODELS,
    LOCAL_PROVIDERS,
    OLLAMA_BASE_URL,
    THEME_COLORS,
    get_all_models,
)


# ---------------------------------------------------------------------------
# Background worker: probe Ollama for installed models
# ---------------------------------------------------------------------------

class _OllamaProbeWorker(QThread):
    """
    Runs in a background thread so the UI never blocks while waiting for
    Ollama's HTTP response.
    """

    probe_done = pyqtSignal(list, str)   # (model_names: list[str], error: str)

    def run(self) -> None:  # noqa: D102
        try:
            import urllib.request, json
            url = f"{OLLAMA_BASE_URL}/api/tags"
            with urllib.request.urlopen(url, timeout=4) as resp:
                data = json.loads(resp.read())
            names = [m["name"] for m in data.get("models", [])]
            self.probe_done.emit(names, "")
        except Exception as exc:  # noqa: BLE001
            self.probe_done.emit([], str(exc))


# ---------------------------------------------------------------------------
# Toggle card: a styled radio button in a framed card
# ---------------------------------------------------------------------------

class _ToggleCard(QFrame):
    """
    A selectable card that wraps a QRadioButton.
    Highlights with the yellow accent when checked.
    """

    def __init__(
        self,
        title: str,
        subtitle: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("toggleCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._radio = QRadioButton()
        self._radio.toggled.connect(self._refresh_style)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(14)

        text_col = QVBoxLayout()
        text_col.setSpacing(3)

        title_lbl = QLabel(title)
        title_lbl.setObjectName("cardTitle")
        sub_lbl = QLabel(subtitle)
        sub_lbl.setObjectName("cardSubtitle")

        text_col.addWidget(title_lbl)
        text_col.addWidget(sub_lbl)

        layout.addLayout(text_col)
        layout.addStretch()
        layout.addWidget(self._radio)

        self._refresh_style(False)

    # Allow clicking anywhere on the card to select it.
    def mousePressEvent(self, event: Any) -> None:  # noqa: N802
        self._radio.setChecked(True)
        super().mousePressEvent(event)

    def radio(self) -> QRadioButton:
        return self._radio

    def is_checked(self) -> bool:
        return self._radio.isChecked()

    def _refresh_style(self, checked: bool) -> None:
        acc = THEME_COLORS["accent"]
        div = THEME_COLORS["divider"]
        border = acc if checked else div
        bg = "#111111" if checked else "#0D0D0D"
        self.setStyleSheet(
            f"""
            QFrame#toggleCard {{
                background-color: {bg};
                border: 1.5px solid {border};
                border-radius: 10px;
            }}
            QLabel#cardTitle {{
                color: {"#FFD54A" if checked else "#F0F0F0"};
                font-size: 14px;
                font-weight: 600;
            }}
            QLabel#cardSubtitle {{
                color: {THEME_COLORS["status_text"]};
                font-size: 12px;
            }}
            QRadioButton {{
                background: transparent;
            }}
            QRadioButton::indicator {{
                width: 18px; height: 18px;
                border-radius: 9px;
                border: 2px solid {"#FFD54A" if checked else "#555"};
                background: {"#FFD54A" if checked else "transparent"};
            }}
            """
        )


# ---------------------------------------------------------------------------
# ModelSetupPage
# ---------------------------------------------------------------------------

class ModelSetupPage(QWidget):
    """
    Provider / model picker page.

    Public API
    ----------
    set_user(user_id, username)   — called by MainWindow after login
    """

    setup_confirmed = pyqtSignal(dict)

    # ------------------------------------------------------------------ init

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._user_id   = ""
        self._username  = ""
        self._probe_worker: _OllamaProbeWorker | None = None
        self._build_ui()
        self._apply_base_styles()
        self._on_cloud_toggled(True)    # Cloud shown by default

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_user(self, user_id: str, username: str) -> None:
        self._user_id  = user_id
        self._username = username
        self._greeting.setText(f"Hi {username}, choose your AI model.")
        self._status_label.setText("")

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addSpacerItem(QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))

        card = QFrame()
        card.setObjectName("setupCard")
        card.setFixedWidth(460)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(36, 36, 36, 36)
        card_layout.setSpacing(18)

        # Header
        self._greeting = QLabel("Choose your AI model.")
        self._greeting.setObjectName("setupGreeting")
        self._greeting.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self._greeting)

        # Toggle cards
        toggle_row = QHBoxLayout()
        toggle_row.setSpacing(12)

        self._cloud_card = _ToggleCard(
            "Cloud AI",
            "Fast · requires API key",
        )
        self._local_card = _ToggleCard(
            "Local AI",
            "Private · requires Ollama",
        )

        # Disable cards when provider group is globally disabled.
        if not ENABLE_CLOUD_MODELS:
            self._cloud_card.setEnabled(False)
            self._cloud_card.setToolTip("Cloud models disabled in config")
        if not ENABLE_LOCAL_MODELS:
            self._local_card.setEnabled(False)
            self._local_card.setToolTip("Local models disabled in config")

        toggle_row.addWidget(self._cloud_card)
        toggle_row.addWidget(self._local_card)
        card_layout.addLayout(toggle_row)

        # Radio group — ensures mutual exclusion
        self._radio_group = QButtonGroup(self)
        self._radio_group.addButton(self._cloud_card.radio(), 0)
        self._radio_group.addButton(self._local_card.radio(), 1)
        self._cloud_card.radio().setChecked(True)
        self._radio_group.idToggled.connect(self._on_radio_toggled)

        # Stacked options panel
        self._options_stack = QStackedWidget()
        self._options_stack.addWidget(self._build_cloud_panel())   # index 0
        self._options_stack.addWidget(self._build_local_panel())   # index 1
        card_layout.addWidget(self._options_stack)

        # Status / error line
        self._status_label = QLabel("")
        self._status_label.setObjectName("statusLabel")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.setWordWrap(True)
        card_layout.addWidget(self._status_label)

        # Start button
        self._start_btn = QPushButton("Start chatting")
        self._start_btn.setObjectName("startBtn")
        self._start_btn.setFixedHeight(46)
        self._start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._start_btn.clicked.connect(self._on_start)
        card_layout.addWidget(self._start_btn)

        # Centre card horizontally
        h_wrap = QHBoxLayout()
        h_wrap.addStretch()
        h_wrap.addWidget(card)
        h_wrap.addStretch()
        root.addLayout(h_wrap)
        root.addSpacerItem(QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))

    # ---- Cloud panel -------------------------------------------------

    def _build_cloud_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        layout.addWidget(self._field_label("Model"))
        self._cloud_combo = QComboBox()
        self._cloud_combo.setObjectName("setupCombo")
        for pid, mid in CLOUD_PROVIDERS.items():
            self._cloud_combo.addItem(mid, userData=pid)
        # Pre-select default
        default_idx = self._cloud_combo.findData(DEFAULT_CLOUD_PROVIDER)
        if default_idx >= 0:
            self._cloud_combo.setCurrentIndex(default_idx)
        layout.addWidget(self._cloud_combo)

        layout.addWidget(self._field_label("API Key"))
        self._api_key_input = QLineEdit()
        self._api_key_input.setObjectName("setupInput")
        self._api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._api_key_input.setPlaceholderText("sk-... or paste your key here")
        # Pre-fill from environment if available
        env_key = (
            os.environ.get("GROQ_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
            or os.environ.get("GOOGLE_API_KEY")
            or ""
        )
        self._api_key_input.setText(env_key)
        layout.addWidget(self._api_key_input)

        return panel

    # ---- Local panel -------------------------------------------------

    def _build_local_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        layout.addWidget(self._field_label("Model"))

        row = QHBoxLayout()
        row.setSpacing(8)

        self._local_combo = QComboBox()
        self._local_combo.setObjectName("setupCombo")
        self._populate_local_combo(list(LOCAL_PROVIDERS.keys()))
        row.addWidget(self._local_combo, stretch=1)

        self._refresh_btn = QPushButton("Refresh")
        self._refresh_btn.setObjectName("refreshBtn")
        self._refresh_btn.setFixedHeight(36)
        self._refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._refresh_btn.setToolTip("Probe Ollama for installed models")
        self._refresh_btn.clicked.connect(self._on_refresh_local)
        row.addWidget(self._refresh_btn)

        layout.addLayout(row)

        ollama_note = QLabel(f"Ollama endpoint: {OLLAMA_BASE_URL}")
        ollama_note.setObjectName("ollamaNote")
        layout.addWidget(ollama_note)

        return panel

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _field_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("fieldLabel")
        return lbl

    def _populate_local_combo(self, provider_ids: list[str]) -> None:
        """Fill local combo from a list of provider_id strings."""
        self._local_combo.clear()
        for pid in provider_ids:
            mid = LOCAL_PROVIDERS.get(pid, pid)
            self._local_combo.addItem(mid, userData=pid)
        default_idx = self._local_combo.findData(DEFAULT_LOCAL_PROVIDER)
        if default_idx >= 0:
            self._local_combo.setCurrentIndex(default_idx)

    def _set_status(self, message: str, error: bool = False) -> None:
        color = "#FF6B6B" if error else THEME_COLORS["status_text"]
        self._status_label.setStyleSheet(f"color: {color}; font-size: 12px;")
        self._status_label.setText(message)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_radio_toggled(self, btn_id: int, checked: bool) -> None:
        if not checked:
            return
        # btn_id 0 = cloud, 1 = local
        self._options_stack.setCurrentIndex(btn_id)
        self._status_label.setText("")

    def _on_cloud_toggled(self, checked: bool) -> None:
        if checked:
            self._options_stack.setCurrentIndex(0)

    def _on_refresh_local(self) -> None:
        if self._probe_worker and self._probe_worker.isRunning():
            return
        self._refresh_btn.setEnabled(False)
        self._refresh_btn.setText("Probing...")
        self._set_status("Connecting to Ollama...")
        self._probe_worker = _OllamaProbeWorker()
        self._probe_worker.probe_done.connect(self._on_probe_done)
        self._probe_worker.start()

    @pyqtSlot(list, str)
    def _on_probe_done(self, model_names: list[str], error: str) -> None:
        self._refresh_btn.setEnabled(True)
        self._refresh_btn.setText("Refresh")

        if error:
            self._set_status(f"Ollama not reachable: {error}", error=True)
            return

        if not model_names:
            self._set_status("Ollama is running but no models are installed.", error=True)
            return

        # Populate combo with whatever Ollama actually has installed,
        # falling back to config provider_id when the name matches.
        self._local_combo.clear()
        reverse = {v: k for k, v in LOCAL_PROVIDERS.items()}
        for name in model_names:
            pid = reverse.get(name, name)   # use stable id if known, else raw name
            self._local_combo.addItem(name, userData=pid)
        self._set_status(f"Found {len(model_names)} model(s) in Ollama.")

    def _on_start(self) -> None:
        self._status_label.setText("")
        use_cloud = self._cloud_card.is_checked()

        if use_cloud:
            session_config = self._build_cloud_config()
        else:
            session_config = self._build_local_config()

        if session_config is None:
            return  # validation failed; status already set

        # Attach user identity so MainWindow can split it out cleanly.
        session_config["user_id"]  = self._user_id
        session_config["username"] = self._username

        self._start_btn.setEnabled(False)
        self._start_btn.setText("Loading...")
        self.setup_confirmed.emit(session_config)

    # ------------------------------------------------------------------
    # Config builders (return None on validation failure)
    # ------------------------------------------------------------------

    def _build_cloud_config(self) -> dict[str, Any] | None:
        api_key = self._api_key_input.text().strip()
        if not api_key:
            self._set_status("Please enter an API key for the cloud model.", error=True)
            self._api_key_input.setFocus()
            return None

        pid = self._cloud_combo.currentData()
        mid = CLOUD_PROVIDERS.get(pid, self._cloud_combo.currentText())
        return {
            "provider_type": "cloud",
            "provider_id":   pid,
            "model_id":      mid,
            "is_local":      False,
            "api_key":       api_key,
        }

    def _build_local_config(self) -> dict[str, Any] | None:
        pid = self._local_combo.currentData() or self._local_combo.currentText()
        mid = LOCAL_PROVIDERS.get(pid, self._local_combo.currentText())
        if not mid:
            self._set_status("No local model selected.", error=True)
            return None
        return {
            "provider_type": "local",
            "provider_id":   pid,
            "model_id":      mid,
            "is_local":      True,
            "api_key":       "",
        }

    # ------------------------------------------------------------------
    # Called by MainWindow after setup_confirmed is handled, so the
    # button resets if the user navigates back via logout.
    # ------------------------------------------------------------------

    def reset_button(self) -> None:
        self._start_btn.setEnabled(True)
        self._start_btn.setText("Start chatting")

    # ------------------------------------------------------------------
    # Styles
    # ------------------------------------------------------------------

    def _apply_base_styles(self) -> None:
        bg  = THEME_COLORS["background"]
        acc = THEME_COLORS["accent"]
        inp = THEME_COLORS["input_bg"]
        txt = THEME_COLORS["bot_bubble_text"]
        div = THEME_COLORS["divider"]
        mut = THEME_COLORS["status_text"]

        self.setStyleSheet(
            f"""
            ModelSetupPage {{
                background-color: {bg};
            }}

            QFrame#setupCard {{
                background-color: #0D0D0D;
                border: 1px solid {div};
                border-radius: 12px;
            }}

            QLabel#setupGreeting {{
                color: {acc};
                font-size: 20px;
                font-weight: 700;
            }}

            QLabel#fieldLabel {{
                color: {mut};
                font-size: 12px;
                font-weight: 500;
            }}

            QLabel#ollamaNote {{
                color: #555555;
                font-size: 11px;
                font-style: italic;
            }}

            QComboBox#setupCombo {{
                background-color: {inp};
                color: {txt};
                border: 1px solid {div};
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 13px;
                selection-background-color: {acc};
            }}

            QComboBox#setupCombo:focus {{
                border: 1.5px solid {acc};
            }}

            QComboBox#setupCombo::drop-down {{
                border: none;
                width: 24px;
            }}

            QComboBox#setupCombo QAbstractItemView {{
                background-color: #1A1A1A;
                color: {txt};
                selection-background-color: {acc};
                selection-color: #000000;
                border: 1px solid {div};
                outline: none;
            }}

            QLineEdit#setupInput {{
                background-color: {inp};
                color: {txt};
                border: 1px solid {div};
                border-radius: 6px;
                padding: 10px 12px;
                font-size: 13px;
                selection-background-color: {acc};
                selection-color: #000000;
            }}

            QLineEdit#setupInput:focus {{
                border: 1.5px solid {acc};
            }}

            QPushButton#startBtn {{
                background-color: {acc};
                color: #000000;
                border: none;
                border-radius: 6px;
                font-size: 15px;
                font-weight: 600;
            }}

            QPushButton#startBtn:hover {{
                background-color: #FFE57A;
            }}

            QPushButton#startBtn:pressed {{
                background-color: #F0C030;
            }}

            QPushButton#startBtn:disabled {{
                background-color: #555555;
                color: #999999;
            }}

            QPushButton#refreshBtn {{
                background-color: transparent;
                color: {acc};
                border: 1.5px solid {acc};
                border-radius: 6px;
                padding: 0 14px;
                font-size: 12px;
                font-weight: 600;
            }}

            QPushButton#refreshBtn:hover {{
                background-color: #1A1600;
            }}

            QPushButton#refreshBtn:disabled {{
                color: #555555;
                border-color: #333333;
            }}

            QLabel#statusLabel {{
                min-height: 18px;
                font-size: 12px;
            }}
            """
        )
