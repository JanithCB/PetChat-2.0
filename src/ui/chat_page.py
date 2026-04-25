"""WhatsApp-style chat page for PetChat-2.0."""

from __future__ import annotations

import re
import uuid
from typing import Any

from PyQt6.QtCore import QObject, Qt, QThread, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpacerItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.config import APP_NAME, MAX_HISTORY_TURNS, MODE_GET_SUPPORT, MODE_HELP_SOMEONE
from src.ui.styles import (
    C,
    GHOST_BTN,
    PRIMARY_BTN,
    STATUS_LABEL,
    apply_bubble_shadow,
    get_bubble_style,
)


def split_reply_into_chunks(text: str, max_chunks: int = 3) -> list[str]:
    text = text.strip()
    if not text:
        return []

    parts = [part.strip() for part in re.split(r"\n{2,}", text) if part.strip()]
    if len(parts) <= 1:
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
        if len(sentences) <= 2:
            parts = [text]
        else:
            groups: list[str] = []
            remaining = list(sentences)
            while remaining and len(groups) < max_chunks:
                slots_left = max_chunks - len(groups)
                take = max(1, round(len(remaining) / slots_left))
                groups.append(" ".join(remaining[:take]).strip())
                remaining = remaining[take:]
            parts = groups

    if len(parts) > max_chunks:
        parts = parts[: max_chunks - 1] + ["\n\n".join(parts[max_chunks - 1 :])]
    return [part for part in parts if part]


class _MessageBubble(QWidget):
    def __init__(self, text: str, role: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._role = role
        self._build(text)

    def _build(self, text: str) -> None:
        outer = QHBoxLayout(self)
        outer.setContentsMargins(12, 4, 12, 4)
        outer.setSpacing(0)

        self._label = QLabel(text)
        self._label.setWordWrap(True)
        self._label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        self._label.setMaximumWidth(520)
        self._label.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Minimum)
        self._label.setStyleSheet(get_bubble_style(self._role))
        apply_bubble_shadow(self._label, blur_radius=14.0, y_offset=2.0)

        spacer = QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        if self._role == "user":
            outer.addWidget(self._label)
            outer.addSpacerItem(spacer)
        else:
            outer.addSpacerItem(spacer)
            outer.addWidget(self._label)


class _ChatWorker(QObject):
    reply_ready = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(
        self,
        mode: str,
        session_config: dict[str, Any],
        history: list[dict[str, str]],
        user_message: str,
        user_info: dict[str, str],
    ) -> None:
        super().__init__()
        self._mode = mode
        self._session_config = dict(session_config)
        self._history = list(history)
        self._user_message = user_message
        self._user_info = dict(user_info)

    @pyqtSlot()
    def run(self) -> None:
        try:
            from src.core.pipeline import run_chat_turn

            result = run_chat_turn(
                mode=self._mode,
                session_config=self._session_config,
                history=self._history,
                user_message=self._user_message,
                user_info=self._user_info,
            )
            if isinstance(result, dict):
                reply = str(result.get("final_reply", "")).strip()
            else:
                reply = str(result).strip()
            self.reply_ready.emit(reply)
        except Exception as exc:  # noqa: BLE001
            self.error_occurred.emit(str(exc))
        finally:
            self.finished.emit()


class ChatPage(QWidget):
    logout_requested = pyqtSignal()
    back_requested = pyqtSignal()

    _FIRST_BUBBLE_DELAY_MS = 280
    _NEXT_BUBBLE_DELAY_MS = 520

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._user_name = ""
        self._mode = MODE_GET_SUPPORT
        self._session_config: dict[str, Any] = {}
        self._user_info: dict[str, str] = {}
        self._history: list[dict[str, str]] = []
        self._pending_chunks: list[str] = []
        self._thread: QThread | None = None
        self._worker: _ChatWorker | None = None

        self._build_ui()
        self._apply_styles()
        self.reset_session()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_header())
        root.addWidget(self._build_conversation(), 1)
        root.addWidget(self._build_footer())

    def _build_header(self) -> QWidget:
        header = QFrame()
        header.setObjectName("chatHeader")
        layout = QVBoxLayout(header)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(10)

        self._title_label = QLabel(APP_NAME)
        self._title_label.setObjectName("titleLabel")
        top_row.addWidget(self._title_label)

        self._session_label = QLabel("")
        self._session_label.setObjectName("sessionLabel")
        top_row.addWidget(self._session_label)
        top_row.addStretch(1)
        layout.addLayout(top_row)

        mode_row = QHBoxLayout()
        mode_row.setContentsMargins(0, 0, 0, 0)
        mode_row.setSpacing(8)

        self._mode_group = QButtonGroup(self)
        self._support_button = QPushButton("Get Support")
        self._support_button.setObjectName("modeButton")
        self._support_button.setCheckable(True)
        self._help_button = QPushButton("Help Someone")
        self._help_button.setObjectName("modeButton")
        self._help_button.setCheckable(True)

        self._mode_group.setExclusive(True)
        self._mode_group.addButton(self._support_button, 0)
        self._mode_group.addButton(self._help_button, 1)
        self._mode_group.buttonClicked.connect(self._on_mode_button_clicked)

        mode_row.addWidget(self._support_button)
        mode_row.addWidget(self._help_button)
        mode_row.addStretch(1)
        layout.addLayout(mode_row)

        return header

    def _build_conversation(self) -> QScrollArea:
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setObjectName("conversationScroll")

        self._conversation_host = QWidget()
        self._conversation_host.setObjectName("conversationHost")
        self._conversation_layout = QVBoxLayout(self._conversation_host)
        self._conversation_layout.setContentsMargins(0, 12, 0, 12)
        self._conversation_layout.setSpacing(2)
        self._conversation_layout.addStretch(1)

        self._scroll.setWidget(self._conversation_host)
        return self._scroll

    def _build_footer(self) -> QWidget:
        footer = QFrame()
        footer.setObjectName("footerFrame")
        layout = QVBoxLayout(footer)
        layout.setContentsMargins(12, 8, 12, 12)
        layout.setSpacing(8)

        self._status_label = QLabel("")
        self._status_label.setObjectName("statusLabel")
        self._status_label.setStyleSheet(STATUS_LABEL)
        layout.addWidget(self._status_label)

        input_row = QHBoxLayout()
        input_row.setContentsMargins(0, 0, 0, 0)
        input_row.setSpacing(10)

        self._input = _MessageInput()
        self._input.setObjectName("chatInput")
        self._input.setPlaceholderText("Type a message")
        self._input.setFixedHeight(48)
        self._input.send_requested.connect(self._on_send)
        input_row.addWidget(self._input, 1)

        self._send_button = QPushButton("Send")
        self._send_button.setObjectName("sendButton")
        self._send_button.setFixedHeight(48)
        self._send_button.setMinimumWidth(96)
        self._send_button.clicked.connect(self._on_send)
        input_row.addWidget(self._send_button)

        layout.addLayout(input_row)
        return footer

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            f"""
            QWidget {{
                background-color: {C.BG};
                color: {C.TEXT};
            }}
            QFrame#chatHeader, QFrame#footerFrame {{
                background-color: {C.BG};
                border: none;
            }}
            QLabel#titleLabel {{
                color: {C.ACCENT};
                font-size: 16px;
                font-weight: 700;
                background: transparent;
            }}
            QLabel#sessionLabel {{
                color: {C.MUTED};
                font-size: 12px;
                background: transparent;
            }}
            QScrollArea#conversationScroll, QWidget#conversationHost {{
                background-color: {C.BG};
                border: none;
            }}
            QTextEdit#chatInput {{
                background-color: {C.INPUT_BG};
                color: {C.INPUT_TEXT};
                border: 1px solid {C.DIVIDER};
                border-radius: 16px;
                padding: 10px 12px;
            }}
            QTextEdit#chatInput:focus {{
                border: 1px solid {C.ACCENT};
            }}
            QPushButton#sendButton {{
                {PRIMARY_BTN}
            }}
            QPushButton#modeButton {{
                {GHOST_BTN}
            }}
            QPushButton#modeButton:checked {{
                background-color: {C.ACCENT};
                color: {C.USER_TEXT};
                border: 1px solid {C.ACCENT};
            }}
            """
        )

    def start_session(
        self,
        user_name: str,
        mode: str,
        session_config: dict[str, Any],
    ) -> None:
        self.shutdown()
        self._user_name = user_name.strip()
        self._mode = mode or MODE_GET_SUPPORT
        self._session_config = dict(session_config)
        self._history = []
        self._pending_chunks = []
        self._user_info = {
            "user_name": self._user_name or "User",
            "user_id": (self._user_name.lower().replace(" ", "_") or "user"),
            "session_id": f"desktop_{uuid.uuid4().hex[:12]}",
        }

        self._clear_conversation()
        self._set_mode_buttons()
        self._session_label.setText(self._session_summary())
        self._status_label.clear()
        self._set_input_enabled(True)
        self._input.clear()
        self._input.setFocus()

    def reset_session(self) -> None:
        self.shutdown()
        self._user_name = ""
        self._mode = MODE_GET_SUPPORT
        self._session_config = {}
        self._user_info = {}
        self._history = []
        self._pending_chunks = []
        self._clear_conversation()
        self._set_mode_buttons()
        self._session_label.clear()
        self._status_label.clear()
        self._input.clear()
        self._set_input_enabled(True)

    def shutdown(self) -> None:
        self._pending_chunks = []
        if self._thread and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(2000)
        self._thread = None
        self._worker = None

    def _session_summary(self) -> str:
        model_id = str(self._session_config.get("model_id", "")).strip()
        provider_type = str(self._session_config.get("provider_type", "")).strip()
        if model_id and provider_type:
            return f"{self._user_name} · {provider_type} · {model_id}"
        if model_id:
            return f"{self._user_name} · {model_id}"
        return self._user_name

    def _on_mode_button_clicked(self, button: QPushButton) -> None:
        if button is self._support_button:
            self._mode = MODE_GET_SUPPORT
        elif button is self._help_button:
            self._mode = MODE_HELP_SOMEONE
        self._status_label.clear()

    def _set_mode_buttons(self) -> None:
        self._support_button.setChecked(self._mode == MODE_GET_SUPPORT)
        self._help_button.setChecked(self._mode == MODE_HELP_SOMEONE)

    def _on_send(self) -> None:
        text = self._input.toPlainText().strip()
        if not text:
            return
        if self._thread and self._thread.isRunning():
            return

        self._input.clear()
        self._append_bubble(text, role="user")
        self._push_history("user", text)
        self._set_input_enabled(False)
        self._show_typing()
        self._start_worker(text)

    def _start_worker(self, user_message: str) -> None:
        self._thread = QThread(self)
        self._worker = _ChatWorker(
            mode=self._mode,
            session_config=self._session_config,
            history=list(self._history),
            user_message=user_message,
            user_info=self._user_info,
        )
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.reply_ready.connect(self._on_reply_ready)
        self._worker.error_occurred.connect(self._on_error)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self._on_thread_finished)
        self._thread.start()

    @pyqtSlot()
    def _on_thread_finished(self) -> None:
        self._thread = None
        self._worker = None

    @pyqtSlot(str)
    def _on_reply_ready(self, reply: str) -> None:
        clean_reply = reply.strip() or "I am here with you."
        self._push_history("assistant", clean_reply)
        chunks = split_reply_into_chunks(clean_reply, max_chunks=3)
        if not chunks:
            chunks = [clean_reply]
        self._pending_chunks = chunks
        QTimer.singleShot(self._FIRST_BUBBLE_DELAY_MS, self._show_next_reply_chunk)

    @pyqtSlot(str)
    def _on_error(self, message: str) -> None:
        self._pending_chunks = []
        self._hide_typing()
        self._set_input_enabled(True)
        self._append_bubble(f"Something went wrong: {message}", role="error")

    def _show_next_reply_chunk(self) -> None:
        if not self._pending_chunks:
            self._hide_typing()
            self._set_input_enabled(True)
            return

        chunk = self._pending_chunks.pop(0)
        self._append_bubble(chunk, role="assistant")
        if self._pending_chunks:
            self._show_typing()
            QTimer.singleShot(self._NEXT_BUBBLE_DELAY_MS, self._show_next_reply_chunk)
        else:
            self._hide_typing()
            self._set_input_enabled(True)

    def _show_typing(self) -> None:
        self._status_label.setText("Companion is typing...")

    def _hide_typing(self) -> None:
        self._status_label.clear()

    def _append_bubble(self, text: str, role: str) -> None:
        insert_index = self._conversation_layout.count() - 1
        self._conversation_layout.insertWidget(insert_index, _MessageBubble(text, role))
        QTimer.singleShot(0, self._scroll_to_bottom)

    def _clear_conversation(self) -> None:
        while self._conversation_layout.count() > 1:
            item = self._conversation_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _scroll_to_bottom(self) -> None:
        bar = self._scroll.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _set_input_enabled(self, enabled: bool) -> None:
        self._input.setEnabled(enabled)
        self._send_button.setEnabled(enabled)
        if enabled:
            self._input.setFocus()

    def _push_history(self, role: str, content: str) -> None:
        self._history.append({"role": role, "content": content})
        max_messages = MAX_HISTORY_TURNS * 2
        if len(self._history) > max_messages:
            self._history = self._history[-max_messages:]


class _MessageInput(QTextEdit):
    send_requested = pyqtSignal()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if (
            event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
            and not event.modifiers() & Qt.KeyboardModifier.ShiftModifier
        ):
            self.send_requested.emit()
            return
        super().keyPressEvent(event)