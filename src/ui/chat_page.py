"""WhatsApp-style chat page for PetChat-2.0."""

from __future__ import annotations

import re
import uuid
from typing import Any

from PyQt6.QtCore import (
    QEasingCurve,
    QObject,
    QPropertyAnimation,
    Qt,
    QThread,
    QTimer,
    pyqtSignal,
    pyqtSlot,
)
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
    apply_input_shadow,
    get_bubble_style,
)

try:
    from src.ui.styles import (
        CHAT_BUBBLE_MAX_WIDTH,
        CHAT_INPUT_CONTAINER,
        CHAT_MAX_WIDTH,
        CHAT_SIDE_PADDING,
        CHAT_TOP_PADDING,
        CHAT_BOTTOM_PADDING,
    )
except ImportError:
    CHAT_MAX_WIDTH = 860
    CHAT_BUBBLE_MAX_WIDTH = 640
    CHAT_SIDE_PADDING = 22
    CHAT_TOP_PADDING = 18
    CHAT_BOTTOM_PADDING = 16
    CHAT_INPUT_CONTAINER = f"""
    QFrame {{
        background-color: {C.SURFACE};
        border: 1px solid {C.DIVIDER};
        border-radius: 18px;
        padding: 8px;
    }}
    """


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
        outer.setContentsMargins(10, 4, 10, 4)
        outer.setSpacing(0)

        self._label = QLabel(text)
        self._label.setWordWrap(True)
        self._label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        self._label.setMaximumWidth(CHAT_BUBBLE_MAX_WIDTH)
        self._label.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Minimum)
        self._label.setStyleSheet(get_bubble_style(self._role))
        apply_bubble_shadow(self._label, blur_radius=16.0, y_offset=2.5)

        spacer = QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        if self._role == "user":
            outer.addSpacerItem(spacer)
            outer.addWidget(self._label)
        else:
            outer.addWidget(self._label)
            outer.addSpacerItem(spacer)


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

    _FIRST_BUBBLE_DELAY_MS = 360
    _NEXT_BUBBLE_DELAY_MS = 560
    _SCROLL_ANIMATION_MS = 260

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._user_name = ""
        self._mode = MODE_GET_SUPPORT
        self._active_worker_mode = MODE_GET_SUPPORT

        self._session_config: dict[str, Any] = {}
        self._user_info: dict[str, str] = {}

        self._mode_histories: dict[str, list[dict[str, str]]] = {
            MODE_GET_SUPPORT: [],
            MODE_HELP_SOMEONE: [],
        }

        self._pending_chunks: list[str] = []
        self._typing_bubble: _MessageBubble | None = None

        self._thread: QThread | None = None
        self._worker: _ChatWorker | None = None
        self._scroll_animation: QPropertyAnimation | None = None

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

        outer = QHBoxLayout(header)
        outer.setContentsMargins(CHAT_SIDE_PADDING, 16, CHAT_SIDE_PADDING, 14)
        outer.setSpacing(0)

        inner = QFrame()
        inner.setObjectName("headerInner")
        inner.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)

        layout = QVBoxLayout(inner)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

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

        outer.addWidget(inner, 1)

        return header

    def _build_conversation(self) -> QScrollArea:
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setObjectName("conversationScroll")

        self._conversation_outer = QWidget()
        self._conversation_outer.setObjectName("conversationOuter")

        outer_layout = QHBoxLayout(self._conversation_outer)
        outer_layout.setContentsMargins(CHAT_SIDE_PADDING, 0, CHAT_SIDE_PADDING, 0)
        outer_layout.setSpacing(0)

        self._conversation_host = QWidget()
        self._conversation_host.setObjectName("conversationHost")
        self._conversation_host.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._conversation_layout = QVBoxLayout(self._conversation_host)
        self._conversation_layout.setContentsMargins(
            0,
            CHAT_TOP_PADDING,
            0,
            CHAT_BOTTOM_PADDING,
        )
        self._conversation_layout.setSpacing(5)
        self._conversation_layout.addStretch(1)

        outer_layout.addWidget(self._conversation_host, 1)

        self._scroll.setWidget(self._conversation_outer)
        return self._scroll

    def _build_footer(self) -> QWidget:
        footer = QFrame()
        footer.setObjectName("footerFrame")

        outer = QHBoxLayout(footer)
        outer.setContentsMargins(CHAT_SIDE_PADDING, 10, CHAT_SIDE_PADDING, 22)
        outer.setSpacing(0)

        inner = QFrame()
        inner.setObjectName("footerInner")
        inner.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)

        layout = QVBoxLayout(inner)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._status_label = QLabel("")
        self._status_label.setObjectName("statusLabel")
        self._status_label.setStyleSheet(STATUS_LABEL)
        layout.addWidget(self._status_label)

        self._input_container = QFrame()
        self._input_container.setObjectName("inputContainer")
        self._input_container.setStyleSheet(CHAT_INPUT_CONTAINER)
        apply_input_shadow(self._input_container, blur_radius=22.0, y_offset=4.0)

        input_row = QHBoxLayout(self._input_container)
        input_row.setContentsMargins(12, 9, 9, 9)
        input_row.setSpacing(10)

        self._input = _MessageInput()
        self._input.setObjectName("chatInput")
        self._input.setPlaceholderText("Type a message")
        self._input.setFixedHeight(54)
        self._input.send_requested.connect(self._on_send)
        input_row.addWidget(self._input, 1)

        self._send_button = QPushButton("Send")
        self._send_button.setObjectName("sendButton")
        self._send_button.setFixedHeight(48)
        self._send_button.setMinimumWidth(104)
        self._send_button.clicked.connect(self._on_send)
        input_row.addWidget(self._send_button)

        layout.addWidget(self._input_container)

        outer.addWidget(inner, 1)

        return footer

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            f"""
            QWidget {{
                background-color: {C.BG};
                color: {C.TEXT};
            }}

            QFrame#chatHeader {{
                background-color: #0D0D0D;
                border-bottom: 1px solid #242015;
            }}

            QFrame#footerFrame {{
                background-color: #0D0D0D;
                border-top: 1px solid #242015;
            }}

            QFrame#headerInner,
            QFrame#footerInner {{
                background-color: transparent;
                border: none;
            }}

            QLabel#titleLabel {{
                color: {C.ACCENT};
                font-size: 22px;
                font-weight: 850;
                background: transparent;
                letter-spacing: -0.4px;
            }}

            QLabel#sessionLabel {{
                color: {C.MUTED};
                font-size: 13px;
                background: transparent;
                padding-top: 4px;
            }}

            QScrollArea#conversationScroll,
            QWidget#conversationOuter,
            QWidget#conversationHost {{
                background-color: {C.BG};
                border: none;
            }}

            QTextEdit#chatInput {{
                background-color: #0F0F0F;
                color: {C.INPUT_TEXT};
                border: 1px solid #342E1F;
                border-radius: 17px;
                padding: 13px 14px;
                font-size: 14px;
            }}

            QTextEdit#chatInput:focus {{
                border: 1px solid {C.ACCENT};
                background-color: #101010;
            }}

            QPushButton#sendButton {{
                background-color: {C.ACCENT};
                color: {C.USER_TEXT};
                border: 1px solid {C.ACCENT};
                border-radius: 16px;
                padding: 10px 18px;
                font-size: 14px;
                font-weight: 750;
            }}

            QPushButton#sendButton:hover {{
                background-color: {C.ACCENT_HOVER};
                border: 1px solid {C.ACCENT_HOVER};
            }}

            QPushButton#sendButton:pressed {{
                background-color: #D6A900;
                border: 1px solid #D6A900;
            }}

            QPushButton#sendButton:disabled {{
                background-color: #2A2A2A;
                color: #777777;
                border: 1px solid #333333;
            }}

            QPushButton#modeButton {{
                background-color: transparent;
                color: {C.ACCENT};
                border: 1px solid {C.DIVIDER};
                border-radius: 15px;
                padding: 10px 18px;
                font-size: 14px;
                font-weight: 650;
            }}

            QPushButton#modeButton:hover {{
                background-color: #1A170E;
                border: 1px solid {C.ACCENT};
            }}

            QPushButton#modeButton:pressed {{
                background-color: #241F10;
            }}

            QPushButton#modeButton:checked {{
                background-color: {C.ACCENT};
                color: {C.USER_TEXT};
                border: 1px solid {C.ACCENT};
            }}

            QPushButton#modeButton:disabled {{
                background-color: #202020;
                color: #686868;
                border: 1px solid #303030;
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
        self._active_worker_mode = self._mode
        self._session_config = dict(session_config)

        self._mode_histories = {
            MODE_GET_SUPPORT: [],
            MODE_HELP_SOMEONE: [],
        }

        base_user_id = self._user_name.lower().replace(" ", "_") or "user"
        session_root = f"desktop_{uuid.uuid4().hex[:12]}"

        self._user_info = {
            "user_name": self._user_name or "User",
            "user_id": base_user_id,
            "session_id": session_root,
        }

        self._pending_chunks = []
        self._clear_conversation()
        self._set_mode_buttons()
        self._session_label.setText(self._session_summary())
        self._status_label.clear()
        self._set_input_enabled(True)
        self._set_mode_switching_enabled(True)
        self._input.clear()
        self._input.setFocus()

    def reset_session(self) -> None:
        self.shutdown()

        self._user_name = ""
        self._mode = MODE_GET_SUPPORT
        self._active_worker_mode = MODE_GET_SUPPORT
        self._session_config = {}
        self._user_info = {}

        self._mode_histories = {
            MODE_GET_SUPPORT: [],
            MODE_HELP_SOMEONE: [],
        }

        self._pending_chunks = []
        self._clear_conversation()
        self._set_mode_buttons()
        self._session_label.clear()
        self._status_label.clear()
        self._input.clear()
        self._set_input_enabled(True)
        self._set_mode_switching_enabled(True)

    def shutdown(self) -> None:
        self._pending_chunks = []
        self._hide_typing()

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
        if self._thread and self._thread.isRunning():
            self._set_mode_buttons()
            return

        if button is self._support_button:
            self._mode = MODE_GET_SUPPORT
        elif button is self._help_button:
            self._mode = MODE_HELP_SOMEONE

        self._status_label.clear()
        self._set_mode_buttons()
        self._render_active_history()
        QTimer.singleShot(40, self._scroll_to_bottom)

    def _set_mode_buttons(self) -> None:
        self._support_button.setChecked(self._mode == MODE_GET_SUPPORT)
        self._help_button.setChecked(self._mode == MODE_HELP_SOMEONE)

    def _set_mode_switching_enabled(self, enabled: bool) -> None:
        self._support_button.setEnabled(enabled)
        self._help_button.setEnabled(enabled)

    def _active_history(self) -> list[dict[str, str]]:
        return self._mode_histories.setdefault(self._mode, [])

    def _worker_history(self) -> list[dict[str, str]]:
        return self._mode_histories.setdefault(self._active_worker_mode, [])

    def _on_send(self) -> None:
        text = self._input.toPlainText().strip()

        if not text:
            return

        if self._thread and self._thread.isRunning():
            return

        self._active_worker_mode = self._mode

        self._input.clear()
        self._append_bubble(text, role="user")
        self._push_history("user", text, mode=self._active_worker_mode)

        self._set_input_enabled(False)
        self._set_mode_switching_enabled(False)
        self._show_typing()
        self._start_worker(text)

    def _start_worker(self, user_message: str) -> None:
        self._thread = QThread(self)

        history_snapshot = list(self._mode_histories.get(self._active_worker_mode, []))
        user_info = dict(self._user_info)
        user_info["session_id"] = f"{self._user_info.get('session_id', 'desktop')}_{self._active_worker_mode}"

        self._worker = _ChatWorker(
            mode=self._active_worker_mode,
            session_config=self._session_config,
            history=history_snapshot,
            user_message=user_message,
            user_info=user_info,
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

        self._push_history("assistant", clean_reply, mode=self._active_worker_mode)

        chunks = split_reply_into_chunks(clean_reply, max_chunks=3)
        self._pending_chunks = chunks or [clean_reply]

        QTimer.singleShot(self._FIRST_BUBBLE_DELAY_MS, self._show_next_reply_chunk)

    @pyqtSlot(str)
    def _on_error(self, message: str) -> None:
        self._pending_chunks = []
        self._hide_typing()
        self._set_input_enabled(True)
        self._set_mode_switching_enabled(True)

        error_text = f"Something went wrong: {message}"
        self._append_bubble(error_text, role="error")

    def _show_next_reply_chunk(self) -> None:
        if not self._pending_chunks:
            self._hide_typing()
            self._set_input_enabled(True)
            self._set_mode_switching_enabled(True)
            return

        chunk = self._pending_chunks.pop(0)

        if self._mode == self._active_worker_mode:
            self._append_bubble(chunk, role="assistant")

        if self._pending_chunks:
            self._show_typing()
            QTimer.singleShot(self._NEXT_BUBBLE_DELAY_MS, self._show_next_reply_chunk)
        else:
            self._hide_typing()
            self._set_input_enabled(True)
            self._set_mode_switching_enabled(True)

    def _show_typing(self) -> None:
        self._status_label.setText("Companion is typing...")

        if self._typing_bubble is not None:
            return

        self._typing_bubble = _MessageBubble("Companion is typing…", "typing")
        insert_index = self._conversation_layout.count() - 1
        self._conversation_layout.insertWidget(insert_index, self._typing_bubble)
        QTimer.singleShot(40, self._scroll_to_bottom)

    def _hide_typing(self) -> None:
        self._status_label.clear()

        if self._typing_bubble is not None:
            self._conversation_layout.removeWidget(self._typing_bubble)
            self._typing_bubble.deleteLater()
            self._typing_bubble = None

    def _append_bubble(self, text: str, role: str) -> None:
        self._hide_typing()

        bubble = _MessageBubble(text, role)
        insert_index = self._conversation_layout.count() - 1
        self._conversation_layout.insertWidget(insert_index, bubble)

        QTimer.singleShot(35, self._scroll_to_bottom)

    def _render_active_history(self) -> None:
        self._clear_conversation()

        for item in self._active_history():
            role = item.get("role", "assistant")
            content = item.get("content", "").strip()

            if not content:
                continue

            if role == "assistant":
                for chunk in split_reply_into_chunks(content, max_chunks=3):
                    self._append_bubble(chunk, role="assistant")
            else:
                self._append_bubble(content, role=role)

    def _clear_conversation(self) -> None:
        self._typing_bubble = None

        while self._conversation_layout.count() > 1:
            item = self._conversation_layout.takeAt(0)
            widget = item.widget()

            if widget is not None:
                widget.deleteLater()

    def _scroll_to_bottom(self) -> None:
        bar = self._scroll.verticalScrollBar()
        end_value = bar.maximum()

        if self._scroll_animation is not None:
            self._scroll_animation.stop()

        self._scroll_animation = QPropertyAnimation(bar, b"value", self)
        self._scroll_animation.setDuration(self._SCROLL_ANIMATION_MS)
        self._scroll_animation.setStartValue(bar.value())
        self._scroll_animation.setEndValue(end_value)
        self._scroll_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._scroll_animation.start()

    def _set_input_enabled(self, enabled: bool) -> None:
        self._input.setEnabled(enabled)
        self._send_button.setEnabled(enabled)

        if enabled:
            self._input.setFocus()

    def _push_history(self, role: str, content: str, mode: str | None = None) -> None:
        target_mode = mode or self._mode
        history = self._mode_histories.setdefault(target_mode, [])

        history.append({"role": role, "content": content})

        max_messages = MAX_HISTORY_TURNS * 2
        if len(history) > max_messages:
            self._mode_histories[target_mode] = history[-max_messages:]


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