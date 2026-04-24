"""
ui/chat_page.py — WhatsApp-style chat interface for PetChat-2.0.

Layout
------
  ┌─────────────────────────────┐
  │  header (model name, logout)│
  ├─────────────────────────────┤
  │  scroll area (bubbles)      │
  ├─────────────────────────────┤
  │  status ("typing…")         │
  ├─────────────────────────────┤
  │  input row  [Send]          │
  └─────────────────────────────┘

Worker threading
----------------
LLMWorker runs core.pipeline.run_chat_turn in a QThread so the GUI never
blocks.  Replies are delivered via reply_ready(text) or error_occurred(msg).

Bubble pacing
-------------
Multi-chunk replies are displayed with ~600 ms gaps between bubbles via
QTimer to simulate natural typing rhythm.
"""

from __future__ import annotations

import re
import textwrap
from typing import Any

from PyQt6.QtCore import (
    QObject,
    QSize,
    Qt,
    QThread,
    QTimer,
    pyqtSignal,
    pyqtSlot,
)
from PyQt6.QtGui import QKeyEvent, QTextOption
from PyQt6.QtWidgets import (
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

from petchat.config import MAX_HISTORY_TURNS, THEME_COLORS


# ---------------------------------------------------------------------------
# Reply chunking helper
# ---------------------------------------------------------------------------

def split_reply_into_chunks(text: str, max_chunks: int = 3) -> list[str]:
    """
    Split a model reply into 2–3 short, natural-feeling bubbles.

    Strategy (in priority order):
    1. Split on paragraph breaks (blank lines).
    2. Split on sentence boundaries if result is still just one chunk.
    3. Cap at max_chunks; merge tail chunks if needed.
    """
    text = text.strip()
    if not text:
        return [""]

    # 1. Paragraph split
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
    if len(paragraphs) >= 2:
        chunks = paragraphs
    else:
        # 2. Sentence split on ". " / "! " / "? "
        sentences = re.split(r"(?<=[.!?])\s+", text)
        sentences = [s.strip() for s in sentences if s.strip()]
        if len(sentences) >= 2:
            # Group into ~equal thirds
            third = max(1, len(sentences) // max_chunks)
            chunks = []
            for i in range(0, len(sentences), third):
                chunks.append(" ".join(sentences[i : i + third]))
        else:
            chunks = [text]

    # 3. Cap
    if len(chunks) > max_chunks:
        # Merge extra chunks into the last one
        chunks = chunks[: max_chunks - 1] + [" ".join(chunks[max_chunks - 1 :])]

    return [c for c in chunks if c]


# ---------------------------------------------------------------------------
# Message bubble widget
# ---------------------------------------------------------------------------

class _BubbleWidget(QWidget):
    """
    A single chat bubble — user (right-aligned) or companion (left-aligned).
    """

    _MAX_BUBBLE_WIDTH = 520   # px

    def __init__(
        self,
        text: str,
        is_user: bool,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._is_user = is_user
        self._build(text)

    def _build(self, text: str) -> None:
        outer = QHBoxLayout(self)
        outer.setContentsMargins(12, 3, 12, 3)
        outer.setSpacing(0)

        bubble = QLabel(text)
        bubble.setWordWrap(True)
        bubble.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        bubble.setMaximumWidth(self._MAX_BUBBLE_WIDTH)
        bubble.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)

        if self._is_user:
            bg   = THEME_COLORS["user_bubble"]
            fg   = THEME_COLORS["user_bubble_text"]
            br   = "18px 18px 4px 18px"
            border = "none"
        else:
            bg   = THEME_COLORS["bot_bubble"]
            fg   = THEME_COLORS["bot_bubble_text"]
            br   = "18px 18px 18px 4px"
            border = f"1px solid {THEME_COLORS['divider']}"

        bubble.setStyleSheet(
            f"""
            QLabel {{
                background-color: {bg};
                color: {fg};
                border: {border};
                border-radius: {br};
                padding: 10px 14px;
                font-size: 14px;
                line-height: 1.5;
            }}
            """
        )

        spacer = QSpacerItem(
            0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
        )
        if self._is_user:
            outer.addSpacerItem(spacer)
            outer.addWidget(bubble)
        else:
            outer.addWidget(bubble)
            outer.addSpacerItem(spacer)


# ---------------------------------------------------------------------------
# LLM worker
# ---------------------------------------------------------------------------

class LLMWorker(QObject):
    """
    Runs core.pipeline.run_chat_turn in a dedicated QThread.

    Signals
    -------
    reply_ready(text: str)
    error_occurred(message: str)
    finished()
    """

    reply_ready    = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    finished       = pyqtSignal()

    def __init__(
        self,
        session_config: dict[str, Any],
        history: list[dict[str, str]],
        user_message: str,
        user_info: dict[str, str],
    ) -> None:
        super().__init__()
        self._session_config = session_config
        self._history        = history
        self._user_message   = user_message
        self._user_info      = user_info

    @pyqtSlot()
    def run(self) -> None:
        try:
            from petchat.core.pipeline import run_chat_turn  # local import keeps startup fast

            reply = run_chat_turn(
                session_config=self._session_config,
                history=self._history,
                user_message=self._user_message,
                user_info=self._user_info,
            )
            self.reply_ready.emit(reply or "")
        except Exception as exc:  # noqa: BLE001
            self.error_occurred.emit(str(exc))
        finally:
            self.finished.emit()


# ---------------------------------------------------------------------------
# ChatPage
# ---------------------------------------------------------------------------

class ChatPage(QWidget):
    """
    Main chat view.

    Public API (called by MainWindow)
    ----------------------------------
    start_session(session_config, user)
    shutdown()

    Signals
    -------
    logout_requested()
    """

    logout_requested = pyqtSignal()

    # Delay between successive companion bubbles (ms)
    _BUBBLE_DELAY_MS = 650

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._session_config: dict[str, Any] = {}
        self._user_info:      dict[str, str] = {}
        self._history:        list[dict[str, str]] = []
        self._pending_chunks: list[str] = []
        self._worker:         LLMWorker | None = None
        self._thread:         QThread | None = None

        self._build_ui()
        self._apply_styles()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start_session(
        self,
        session_config: dict[str, Any],
        user_info: dict[str, str],
    ) -> None:
        """Called by MainWindow before this page becomes visible."""
        self._session_config = session_config
        self._user_info      = user_info
        self._history        = []
        self._clear_bubbles()
        self._status_label.setText("")
        model_label = session_config.get("model_id", "")
        self._model_badge.setText(model_label)
        self._input.setFocus()

    def shutdown(self) -> None:
        """Clean up background thread on window close."""
        if self._thread and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(2000)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_header())
        root.addWidget(self._build_scroll_area(), stretch=1)
        root.addWidget(self._build_status_bar())
        root.addWidget(self._build_input_row())

    def _build_header(self) -> QWidget:
        header = QFrame()
        header.setObjectName("chatHeader")
        header.setFixedHeight(52)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(10)

        name_lbl = QLabel("PetChat")
        name_lbl.setObjectName("headerName")

        self._model_badge = QLabel("")
        self._model_badge.setObjectName("modelBadge")

        layout.addWidget(name_lbl)
        layout.addWidget(self._model_badge)
        layout.addStretch()

        logout_btn = QPushButton("Logout")
        logout_btn.setObjectName("logoutBtn")
        logout_btn.setFixedHeight(32)
        logout_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        logout_btn.clicked.connect(self._on_logout)
        layout.addWidget(logout_btn)

        return header

    def _build_scroll_area(self) -> QScrollArea:
        self._scroll = QScrollArea()
        self._scroll.setObjectName("chatScroll")
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._bubble_container = QWidget()
        self._bubble_container.setObjectName("bubbleContainer")
        self._bubble_layout = QVBoxLayout(self._bubble_container)
        self._bubble_layout.setContentsMargins(0, 12, 0, 12)
        self._bubble_layout.setSpacing(4)
        self._bubble_layout.addStretch()   # pushes bubbles to the bottom initially

        self._scroll.setWidget(self._bubble_container)
        return self._scroll

    def _build_status_bar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(24)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 16, 0)

        self._status_label = QLabel("")
        self._status_label.setObjectName("statusLabel")
        layout.addWidget(self._status_label)

        return bar

    def _build_input_row(self) -> QWidget:
        row = QFrame()
        row.setObjectName("inputRow")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(12, 8, 12, 12)
        layout.setSpacing(10)

        self._input = _SmartTextEdit()
        self._input.setObjectName("chatInput")
        self._input.setPlaceholderText("Type a message...")
        self._input.setFixedHeight(44)
        self._input.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._input.send_triggered.connect(self._on_send)
        layout.addWidget(self._input, stretch=1)

        self._send_btn = QPushButton("Send")
        self._send_btn.setObjectName("sendBtn")
        self._send_btn.setFixedSize(72, 44)
        self._send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._send_btn.clicked.connect(self._on_send)
        layout.addWidget(self._send_btn)

        return row

    # ------------------------------------------------------------------
    # Bubble helpers
    # ------------------------------------------------------------------

    def _add_bubble(self, text: str, is_user: bool) -> None:
        # Insert before the trailing stretch item (index = count - 1)
        insert_pos = self._bubble_layout.count() - 1
        self._bubble_layout.insertWidget(insert_pos, _BubbleWidget(text, is_user))
        QTimer.singleShot(0, self._scroll_to_bottom)

    def _clear_bubbles(self) -> None:
        while self._bubble_layout.count() > 1:  # keep trailing stretch
            item = self._bubble_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _scroll_to_bottom(self) -> None:
        bar = self._scroll.verticalScrollBar()
        bar.setValue(bar.maximum())

    # ------------------------------------------------------------------
    # Typing animation
    # ------------------------------------------------------------------

    def _show_typing(self) -> None:
        self._status_label.setText("Companion is typing...")

    def _hide_typing(self) -> None:
        self._status_label.setText("")

    def _deliver_chunks(self, chunks: list[str]) -> None:
        """Queue companion bubbles with _BUBBLE_DELAY_MS gaps."""
        self._pending_chunks = list(chunks)
        self._schedule_next_chunk()

    def _schedule_next_chunk(self) -> None:
        if not self._pending_chunks:
            self._hide_typing()
            self._set_input_enabled(True)
            return
        chunk = self._pending_chunks.pop(0)
        self._add_bubble(chunk, is_user=False)
        if self._pending_chunks:
            QTimer.singleShot(self._BUBBLE_DELAY_MS, self._schedule_next_chunk)
        else:
            self._hide_typing()
            self._set_input_enabled(True)

    # ------------------------------------------------------------------
    # History management
    # ------------------------------------------------------------------

    def _push_history(self, role: str, content: str) -> None:
        self._history.append({"role": role, "content": content})
        # Keep only the last MAX_HISTORY_TURNS turns (1 turn = 1 user + 1 assistant)
        max_msgs = MAX_HISTORY_TURNS * 2
        if len(self._history) > max_msgs:
            self._history = self._history[-max_msgs:]

    # ------------------------------------------------------------------
    # Slot: send
    # ------------------------------------------------------------------

    def _on_send(self) -> None:
        text = self._input.toPlainText().strip()
        if not text:
            return
        if self._thread and self._thread.isRunning():
            return  # ignore while a reply is in flight

        self._input.clear()
        self._add_bubble(text, is_user=True)
        self._push_history("user", text)
        self._set_input_enabled(False)
        self._show_typing()
        self._start_worker(text)

    # ------------------------------------------------------------------
    # Worker lifecycle
    # ------------------------------------------------------------------

    def _start_worker(self, message: str) -> None:
        self._thread = QThread()
        self._worker = LLMWorker(
            session_config=self._session_config,
            history=list(self._history),   # pass a snapshot
            user_message=message,
            user_info=self._user_info,
        )
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.reply_ready.connect(self._on_reply_ready)
        self._worker.error_occurred.connect(self._on_error)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    @pyqtSlot(str)
    def _on_reply_ready(self, reply: str) -> None:
        self._push_history("assistant", reply)
        chunks = split_reply_into_chunks(reply)
        self._deliver_chunks(chunks)

    @pyqtSlot(str)
    def _on_error(self, message: str) -> None:
        self._hide_typing()
        self._set_input_enabled(True)
        self._add_bubble(f"[Error: {message}]", is_user=False)

    # ------------------------------------------------------------------
    # Slot: logout
    # ------------------------------------------------------------------

    def _on_logout(self) -> None:
        self.shutdown()
        self.logout_requested.emit()

    # ------------------------------------------------------------------
    # UI state helpers
    # ------------------------------------------------------------------

    def _set_input_enabled(self, enabled: bool) -> None:
        self._input.setEnabled(enabled)
        self._send_btn.setEnabled(enabled)
        if enabled:
            self._input.setFocus()

    # ------------------------------------------------------------------
    # Styles
    # ------------------------------------------------------------------

    def _apply_styles(self) -> None:
        bg  = THEME_COLORS["background"]
        acc = THEME_COLORS["accent"]
        inp = THEME_COLORS["input_bg"]
        txt = THEME_COLORS["bot_bubble_text"]
        div = THEME_COLORS["divider"]
        mut = THEME_COLORS["status_text"]

        self.setStyleSheet(
            f"""
            ChatPage, QWidget#bubbleContainer {{
                background-color: {bg};
            }}

            QFrame#chatHeader {{
                background-color: #0A0A0A;
                border-bottom: 1px solid {div};
            }}

            QLabel#headerName {{
                color: {acc};
                font-size: 16px;
                font-weight: 700;
                letter-spacing: 0.5px;
            }}

            QLabel#modelBadge {{
                color: {mut};
                font-size: 11px;
                background-color: #1A1A1A;
                border: 1px solid {div};
                border-radius: 10px;
                padding: 2px 8px;
            }}

            QPushButton#logoutBtn {{
                color: {mut};
                background: transparent;
                border: 1px solid #333333;
                border-radius: 5px;
                padding: 0 10px;
                font-size: 12px;
            }}

            QPushButton#logoutBtn:hover {{
                color: #FF6B6B;
                border-color: #FF6B6B;
            }}

            QScrollArea#chatScroll {{
                background-color: {bg};
                border: none;
            }}

            QLabel#statusLabel {{
                color: {mut};
                font-size: 12px;
                font-style: italic;
            }}

            QFrame#inputRow {{
                background-color: #0A0A0A;
                border-top: 1px solid {div};
            }}

            QTextEdit#chatInput {{
                background-color: {inp};
                color: {txt};
                border: 1px solid {div};
                border-radius: 22px;
                padding: 10px 16px;
                font-size: 14px;
                selection-background-color: {acc};
                selection-color: #000000;
            }}

            QTextEdit#chatInput:focus {{
                border: 1.5px solid {acc};
            }}

            QPushButton#sendBtn {{
                background-color: {acc};
                color: #000000;
                border: none;
                border-radius: 22px;
                font-size: 14px;
                font-weight: 700;
            }}

            QPushButton#sendBtn:hover {{
                background-color: #FFE57A;
            }}

            QPushButton#sendBtn:pressed {{
                background-color: #F0C030;
            }}

            QPushButton#sendBtn:disabled {{
                background-color: #333333;
                color: #666666;
            }}
            """
        )


# ---------------------------------------------------------------------------
# Smart text-edit: Enter sends, Shift+Enter inserts newline
# ---------------------------------------------------------------------------

class _SmartTextEdit(QTextEdit):
    """QTextEdit that emits send_triggered on plain Enter."""

    send_triggered = pyqtSignal()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if (
            event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
            and not event.modifiers() & Qt.KeyboardModifier.ShiftModifier
        ):
            self.send_triggered.emit()
            return
        super().keyPressEvent(event)
