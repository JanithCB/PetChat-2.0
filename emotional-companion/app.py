import os
import sys
import json
import re
import hashlib
from pathlib import Path

from prompts import (
    SYSTEM_PROMPT,
    MAX_HISTORY_TURNS,
    build_user_message,
    build_rewrite_prompt,
)
from safety import detect_risk_level, build_safety_reply
from esc_support import build_esc_support_plan

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QEvent
from PyQt6.QtGui import QFont, QTextCursor, QTextOption
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QStackedWidget,
    QMessageBox,
    QFrame,
)

from groq import Groq

try:
    from rag_engine import build_rag_context
except Exception:
    build_rag_context = None


APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"
USERS_FILE = DATA_DIR / "users.json"

GROQ_MODEL = "llama-3.3-70b-versatile"


def ensure_data_files():
    DATA_DIR.mkdir(exist_ok=True)
    if not USERS_FILE.exists():
        USERS_FILE.write_text("[]", encoding="utf-8")


def load_users():
    ensure_data_files()
    try:
        return json.loads(USERS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def save_users(users):
    ensure_data_files()
    USERS_FILE.write_text(json.dumps(users, indent=2), encoding="utf-8")


def hash_password(password):
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def resolve_api_key(input_key):
    typed_key = input_key.strip()
    if typed_key:
        return typed_key
    return os.getenv("GROQ_API_KEY") or ""


def normalize_error_text(error_text):
    if not error_text:
        return "Something went wrong."

    lowered = error_text.lower()

    if "429" in lowered or "rate limit" in lowered or "quota" in lowered:
        return (
            "Groq hit a rate limit for a moment.\n\n"
            "Give it a few seconds, then try again."
        )

    if (
        "api key" in lowered
        or "authentication" in lowered
        or "unauthorized" in lowered
        or "permission" in lowered
    ):
        return (
            "The Groq API key looks invalid or unavailable.\n\n"
            "Check that the key is correct and active."
        )

    if "network" in lowered or "timeout" in lowered or "connection" in lowered:
        return (
            "The request got interrupted by a network problem.\n\n"
            "Check your connection and try again."
        )

    return "The message could not be sent right now."


def strip_emojis(text: str) -> str:
    if not text:
        return text

    emoji_pattern = re.compile(
        "["
        "\U0001F300-\U0001F5FF"
        "\U0001F600-\U0001F64F"
        "\U0001F680-\U0001F6FF"
        "\U0001F700-\U0001F77F"
        "\U0001F780-\U0001F7FF"
        "\U0001F800-\U0001F8FF"
        "\U0001F900-\U0001F9FF"
        "\U0001FA00-\U0001FAFF"
        "\U00002600-\U000026FF"
        "\U00002700-\U000027BF"
        "]+",
        flags=re.UNICODE,
    )
    return emoji_pattern.sub("", text).strip()


def parse_risk_result(result):
    if isinstance(result, tuple):
        if len(result) >= 2:
            return (result[0] or "none"), (result[1] or [])
        if len(result) == 1:
            return (result[0] or "none"), []
    if isinstance(result, str):
        return result or "none", []
    return "none", []


def safe_build_safety_reply(risk_level, user_name="there", tags=None):
    try:
        return build_safety_reply(
            risk_level=risk_level,
            user_name=user_name,
            tags=tags or [],
        )
    except TypeError:
        try:
            return build_safety_reply(user_name=user_name)
        except TypeError:
            return build_safety_reply()


def rewrite_friend_style(client, user_message, draft_reply, support_plan=None):
    rewrite_prompt = build_rewrite_prompt(user_message, draft_reply, support_plan)

    completion = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You rewrite chatbot replies to sound like a real, caring person texting.\n"
                    "Keep it warm, natural, and emotionally present.\n"
                    "Do not sound scripted, robotic, or overly structured.\n"
                    "Follow the support plan gently, not rigidly.\n"
                    "Let the reply flow like a real human message."
                ),
            },
            {"role": "user", "content": rewrite_prompt},
        ],
        temperature=0.9,
        max_tokens=300,
    )

    return (completion.choices[0].message.content or "").strip()


class GroqWorker(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, api_key, history, user_message, user_name="there", parent=None):
        super().__init__(parent)
        self.api_key = api_key
        self.history = list(history or [])
        self.user_message = user_message
        self.user_name = user_name

    def run(self):
        try:
            client = Groq(api_key=self.api_key) if self.api_key else Groq()

            risk_result = detect_risk_level(self.user_message)
            risk_level, risk_tags = parse_risk_result(risk_result)

            if risk_level == "high":
                final_reply = safe_build_safety_reply(
                    risk_level=risk_level,
                    user_name=self.user_name,
                    tags=risk_tags,
                )
                self.finished.emit(final_reply.strip())
                return

            support_plan = build_esc_support_plan(
                history=self.history,
                user_message=self.user_message,
                risk_level=risk_level,
            )

            rag_context = ""
            if build_rag_context is not None:
                try:
                    rag_context = build_rag_context(self.user_message)
                except Exception:
                    rag_context = ""

            messages = [
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT,
                }
            ]

            recent_history = self.history[-MAX_HISTORY_TURNS:]
            for role, text in recent_history:
                mapped_role = "assistant" if role == "model" else "user"
                messages.append({"role": mapped_role, "content": text})

            final_user_message = build_user_message(
                self.user_message,
                rag_context,
                support_plan,
            )
            messages.append({"role": "user", "content": final_user_message})

            completion = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=messages,
                temperature=0.7,
                max_tokens=320,
            )

            draft_reply = (completion.choices[0].message.content or "").strip()

            if not draft_reply:
                draft_reply = "I'm here with you. Say that again in your own words."

            try:
                final_reply = rewrite_friend_style(
                    client,
                    self.user_message,
                    draft_reply,
                    support_plan,
                )
                if not final_reply:
                    final_reply = draft_reply
            except Exception:
                final_reply = draft_reply

            should_strip = False

            if risk_level in {"medium", "high"}:
                should_strip = True
            elif not support_plan or not support_plan.get("emoji"):
                should_strip = True

            if should_strip:
                final_reply = strip_emojis(final_reply)

            self.finished.emit(final_reply.strip())

        except Exception as e:
            self.error.emit(str(e))

class AuthPage(QWidget):
    auth_success = pyqtSignal(dict, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.mode = "login"
        self.build_ui()

    def build_ui(self):
        root = QVBoxLayout()
        root.setContentsMargins(40, 28, 40, 28)

        brand_wrap = QVBoxLayout()
        brand_wrap.setSpacing(6)

        brand = QLabel("Companion")
        brand.setFont(QFont("Segoe UI", 26, QFont.Weight.Bold))
        brand.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand.setStyleSheet("color: #facc15; letter-spacing: 1px;")

        brand_sub = QLabel("A quiet space to talk")
        brand_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand_sub.setStyleSheet("color: #52525b; font-size: 10pt; letter-spacing: 0.5px;")

        brand_wrap.addWidget(brand)
        brand_wrap.addWidget(brand_sub)

        card_wrap = QHBoxLayout()
        card_wrap.addStretch()

        self.card = QFrame()
        self.card.setFixedWidth(440)
        self.card.setObjectName("AuthCard")

        card_layout = QVBoxLayout()
        card_layout.setContentsMargins(30, 30, 30, 30)
        card_layout.setSpacing(14)

        self.title = QLabel("Welcome back")
        self.title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.subtitle = QLabel("Login to continue")
        self.subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.subtitle.setStyleSheet("color: #a1a1aa;")

        self.name_label = QLabel("Full name")
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Your name")
        self.name_label.hide()
        self.name_input.hide()

        self.username_label = QLabel("Username")
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Enter username")

        self.password_label = QLabel("Password")
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Enter password")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)

        self.api_label = QLabel("Groq API key")
        self.api_input = QLineEdit()
        self.api_input.setPlaceholderText("Leave empty to use GROQ_API_KEY")
        self.api_input.setEchoMode(QLineEdit.EchoMode.Password)

        env_key = os.getenv("GROQ_API_KEY")
        if env_key:
            self.api_input.setPlaceholderText("Environment key found. You can leave this empty.")

        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #f87171;")
        self.error_label.setWordWrap(True)

        self.primary_button = QPushButton("Login")
        self.primary_button.clicked.connect(self.submit)

        self.switch_button = QPushButton("Create account")
        self.switch_button.setObjectName("GhostButton")
        self.switch_button.clicked.connect(self.toggle_mode)

        card_layout.addWidget(self.title)
        card_layout.addWidget(self.subtitle)
        card_layout.addSpacing(4)
        card_layout.addWidget(self.name_label)
        card_layout.addWidget(self.name_input)
        card_layout.addWidget(self.username_label)
        card_layout.addWidget(self.username_input)
        card_layout.addWidget(self.password_label)
        card_layout.addWidget(self.password_input)
        card_layout.addWidget(self.api_label)
        card_layout.addWidget(self.api_input)
        card_layout.addWidget(self.error_label)
        card_layout.addSpacing(6)
        card_layout.addWidget(self.primary_button)
        card_layout.addWidget(self.switch_button)

        self.card.setLayout(card_layout)
        card_wrap.addWidget(self.card)
        card_wrap.addStretch()

        root.addStretch()
        root.addLayout(brand_wrap)
        root.addSpacing(18)
        root.addLayout(card_wrap)
        root.addStretch()

        self.setLayout(root)

    def toggle_mode(self):
        self.mode = "signup" if self.mode == "login" else "login"
        is_signup = self.mode == "signup"

        self.name_label.setVisible(is_signup)
        self.name_input.setVisible(is_signup)

        if is_signup:
            self.title.setText("Create account")
            self.subtitle.setText("Set up your space")
            self.primary_button.setText("Create account")
            self.switch_button.setText("Already have an account?")
        else:
            self.title.setText("Welcome back")
            self.subtitle.setText("Login to continue")
            self.primary_button.setText("Login")
            self.switch_button.setText("Create account")

        self.error_label.setText("")

    def submit(self):
        users = load_users()

        username = self.username_input.text().strip()
        password = self.password_input.text().strip()
        api_key = resolve_api_key(self.api_input.text())

        if self.mode == "signup":
            full_name = self.name_input.text().strip()

            if not full_name:
                self.error_label.setText("Please enter your full name.")
                return

            if not username:
                self.error_label.setText("Please enter a username.")
                return

            if len(username) < 3:
                self.error_label.setText("Username must be at least 3 characters.")
                return

            if not password:
                self.error_label.setText("Please enter a password.")
                return

            if len(password) < 4:
                self.error_label.setText("Password must be at least 4 characters.")
                return

            if not api_key:
                self.error_label.setText("Please paste your Groq API key or set GROQ_API_KEY.")
                return

            if any(user["username"].lower() == username.lower() for user in users):
                self.error_label.setText("That username already exists.")
                return

            new_user = {
                "full_name": full_name,
                "username": username,
                "password_hash": hash_password(password),
            }
            users.append(new_user)
            save_users(users)
            self.error_label.setText("")
            self.auth_success.emit(new_user, api_key)
            return

        if not username:
            self.error_label.setText("Please enter your username.")
            return

        if not password:
            self.error_label.setText("Please enter your password.")
            return

        if not api_key:
            self.error_label.setText("Please paste your Groq API key or set GROQ_API_KEY.")
            return

        for user in users:
            if (
                user["username"].lower() == username.lower()
                and user["password_hash"] == hash_password(password)
            ):
                self.error_label.setText("")
                self.auth_success.emit(user, api_key)
                return

        self.error_label.setText("Invalid username or password.")


class ChatPage(QWidget):
    sign_out = pyqtSignal()

    def __init__(self, user, api_key, parent=None):
        super().__init__(parent)
        self.user = user
        self.api_key = api_key
        self.history = []
        self.worker = None
        self.request_in_progress = False
        self.pending_user_text = None
        self.build_ui()

    def build_ui(self):
        root = QVBoxLayout()
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        topbar = QFrame()
        topbar.setObjectName("TopBar")
        topbar_layout = QHBoxLayout()
        topbar_layout.setContentsMargins(20, 14, 20, 14)
        topbar_layout.setSpacing(12)

        initials = "".join(p[0].upper() for p in self.user["full_name"].split()[:2])
        avatar = QLabel(initials)
        avatar.setFixedSize(38, 38)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setObjectName("Avatar")

        left_block = QVBoxLayout()
        left_block.setSpacing(1)

        title = QLabel("Companion")
        title.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))

        subtitle = QLabel(f"Hi, {self.user['full_name'].split()[0]} · Ready to listen")
        subtitle.setStyleSheet("color: #a1a1aa; font-size: 10pt;")

        left_block.addWidget(title)
        left_block.addWidget(subtitle)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #facc15; font-size: 10pt;")

        self.clear_button = QPushButton("Clear chat")
        self.clear_button.setObjectName("GhostButton")
        self.clear_button.setFixedHeight(34)
        self.clear_button.clicked.connect(self.clear_chat)

        self.signout_button = QPushButton("Sign out")
        self.signout_button.setObjectName("GhostButton")
        self.signout_button.setFixedHeight(34)
        self.signout_button.clicked.connect(self.sign_out.emit)

        topbar_layout.addWidget(avatar)
        topbar_layout.addLayout(left_block)
        topbar_layout.addStretch()
        topbar_layout.addWidget(self.status_label)
        topbar_layout.addSpacing(4)
        topbar_layout.addWidget(self.clear_button)
        topbar_layout.addWidget(self.signout_button)
        topbar.setLayout(topbar_layout)

        self.chat_view = QTextEdit()
        self.chat_view.setReadOnly(True)
        self.chat_view.setObjectName("ChatView")
        self.chat_view.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)

        input_wrap = QFrame()
        input_wrap.setObjectName("InputWrap")
        input_outer = QVBoxLayout()
        input_outer.setContentsMargins(16, 10, 16, 10)
        input_outer.setSpacing(6)

        self.input_box = QTextEdit()
        self.input_box.setFixedHeight(78)
        self.input_box.setPlaceholderText("Talk freely… Press Enter to send, Shift+Enter for a new line.")
        self.input_box.setObjectName("InputBox")
        self.input_box.installEventFilter(self)

        hint_row = QHBoxLayout()
        hint_row.setSpacing(8)

        hint = QLabel("Enter to send · Shift+Enter for new line")
        hint.setStyleSheet("color: #52525b; font-size: 9pt;")

        self.send_button = QPushButton("Send →")
        self.send_button.setFixedWidth(100)
        self.send_button.setFixedHeight(34)
        self.send_button.clicked.connect(self.handle_send)

        hint_row.addWidget(hint)
        hint_row.addStretch()
        hint_row.addWidget(self.send_button)

        input_outer.addWidget(self.input_box)
        input_outer.addLayout(hint_row)
        input_wrap.setLayout(input_outer)

        root.addWidget(topbar)
        root.addWidget(self.chat_view, stretch=1)
        root.addWidget(input_wrap)
        self.setLayout(root)

        self.append_system_message("This space is private, calm, and here for you.")

    def eventFilter(self, obj, event):
        if obj == self.input_box and event.type() == QEvent.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                    return False
                self.handle_send()
                return True
        return super().eventFilter(obj, event)

    def clear_chat(self):
        if self.request_in_progress:
            return
        self.history = []
        self.pending_user_text = None
        self.chat_view.clear()
        self.append_system_message("The conversation was cleared. You can start again anytime.")

    def append_message(self, sender, text):
        cursor = self.chat_view.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.chat_view.setTextCursor(cursor)

        if sender == "user":
            label = self.user["full_name"]
            label_color = "#facc15"
            bubble_bg = "#1c1a08"
            bubble_border = "#3a3410"
            border_radius = "14px 4px 14px 14px"
        else:
            label = "Companion"
            label_color = "#d4d4d8"
            bubble_bg = "#1a1a1a"
            bubble_border = "#2e2e2e"
            border_radius = "4px 14px 14px 14px"

        escaped = self.escape_html(text).replace(chr(10), "<br>")

        if sender == "user":
            html = (
                '<table width="100%" cellspacing="0" cellpadding="0" style="margin-bottom:12px;">'
                "<tr>"
                '<td width="20%"></td>'
                '<td width="80%" align="right">'
                f'<div style="color:{label_color}; font-weight:600; font-size:9pt; margin-bottom:4px; text-align:right;">{self.escape_html(label)}</div>'
                '<table cellspacing="0" cellpadding="0" align="right"><tr>'
                f'<td style="background:{bubble_bg}; border:1px solid {bubble_border}; border-radius:{border_radius}; padding:10px 13px; color:#efefef; line-height:1.55;">'
                f"{escaped}"
                "</td></tr></table>"
                "</td>"
                "</tr></table>"
            )
        else:
            html = (
                '<table width="100%" cellspacing="0" cellpadding="0" style="margin-bottom:12px;">'
                "<tr>"
                '<td width="80%" align="left">'
                f'<div style="color:{label_color}; font-weight:600; font-size:9pt; margin-bottom:4px; text-align:left;">{self.escape_html(label)}</div>'
                '<table cellspacing="0" cellpadding="0" align="left"><tr>'
                f'<td style="background:{bubble_bg}; border:1px solid {bubble_border}; border-radius:{border_radius}; padding:10px 13px; color:#efefef; line-height:1.55;">'
                f"{escaped}"
                "</td></tr></table>"
                "</td>"
                '<td width="20%"></td>'
                "</tr></table>"
            )

        self.chat_view.insertHtml(html)
        self.chat_view.verticalScrollBar().setValue(
            self.chat_view.verticalScrollBar().maximum()
        )

    def append_system_message(self, text):
        self.chat_view.insertHtml(
            f"""
            <div style="margin: 8px 0 18px 0; text-align:center;">
                <span style="display:inline-block; color:#52525b; font-size:9pt;
                             background:#161616; border:1px solid #222; border-radius:20px;
                             padding:4px 14px;">
                    {self.escape_html(text)}
                </span>
            </div>
            """
        )
        self.chat_view.verticalScrollBar().setValue(
            self.chat_view.verticalScrollBar().maximum()
        )

    @staticmethod
    def escape_html(text):
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    def handle_send(self):
        if self.request_in_progress:
            return

        user_text = self.input_box.toPlainText().strip()
        if not user_text:
            return

        self.request_in_progress = True
        self.pending_user_text = user_text
        self.append_message("user", user_text)
        self.input_box.clear()

        self.send_button.setEnabled(False)
        self.input_box.setEnabled(False)
        self.clear_button.setEnabled(False)
        self.signout_button.setEnabled(False)
        self.status_label.setText("● thinking…")

        self.worker = GroqWorker(
            api_key=self.api_key,
            history=self.history,
            user_message=user_text,
            user_name=self.user["full_name"].split()[0],
        )
        self.worker.finished.connect(self.on_reply)
        self.worker.error.connect(self.on_error)
        self.worker.start()

    def on_reply(self, reply_text):
        self.request_in_progress = False

        if not reply_text:
            reply_text = "I am still here with you. Could you say that in another way?"

        if self.pending_user_text:
            self.history.append(("user", self.pending_user_text))
        self.history.append(("model", reply_text))

        self.pending_user_text = None
        self.append_message("model", reply_text)
        self.status_label.setText("")
        self.send_button.setEnabled(True)
        self.input_box.setEnabled(True)
        self.clear_button.setEnabled(True)
        self.signout_button.setEnabled(True)
        self.input_box.setFocus()
        self.worker = None

    def on_error(self, error_text):
        self.request_in_progress = False
        self.pending_user_text = None
        self.status_label.setText("")
        self.send_button.setEnabled(True)
        self.input_box.setEnabled(True)
        self.clear_button.setEnabled(True)
        self.signout_button.setEnabled(True)
        self.input_box.setFocus()
        self.worker = None

        message = QMessageBox(self)
        message.setIcon(QMessageBox.Icon.Warning)
        message.setWindowTitle("Request failed")
        message.setText(normalize_error_text(error_text))
        if error_text:
            message.setInformativeText(error_text[:1200])
        message.exec()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        ensure_data_files()

        self.stack = QStackedWidget()
        self.auth_page = AuthPage()
        self.chat_page = None

        self.stack.addWidget(self.auth_page)
        self.setCentralWidget(self.stack)

        self.auth_page.auth_success.connect(self.open_chat)

        self.setWindowTitle("Companion")
        self.resize(1020, 740)
        self.setMinimumSize(900, 640)
        self.apply_theme()

    def apply_theme(self):
        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                background-color: #111111;
                color: #f5f5f5;
                font-family: Segoe UI, Arial;
                font-size: 11pt;
            }

            QFrame#AuthCard {
                background-color: #171717;
                border: 1px solid #262626;
                border-radius: 16px;
            }

            QFrame#TopBar {
                background-color: #151515;
                border: none;
                border-bottom: 1px solid #222222;
                border-radius: 0px;
            }

            QFrame#InputWrap {
                background-color: #151515;
                border: none;
                border-top: 1px solid #222222;
                border-radius: 0px;
            }

            QLabel#Avatar {
                background-color: #2a2600;
                color: #facc15;
                border: 1.5px solid #facc1555;
                border-radius: 19px;
                font-weight: 700;
                font-size: 13pt;
            }

            QLabel {
                color: #f5f5f5;
            }

            QLineEdit, QTextEdit {
                background-color: #121212;
                color: #f5f5f5;
                border: 1px solid #2b2b2b;
                border-radius: 10px;
                padding: 10px;
                selection-background-color: #facc15;
                selection-color: #111111;
            }

            QLineEdit:focus, QTextEdit:focus {
                border: 1px solid #facc15;
            }

            QTextEdit#ChatView {
                background-color: #0f0f0f;
                border: none;
                border-radius: 0px;
                padding: 20px 24px;
            }

            QTextEdit#InputBox {
                background-color: #1a1a1a;
                border: 1px solid #2b2b2b;
                border-radius: 10px;
                padding: 10px 12px;
                font-size: 11pt;
            }

            QTextEdit#InputBox:focus {
                border: 1px solid #facc1588;
            }

            QPushButton {
                background-color: #facc15;
                color: #000000;
                border: none;
                border-radius: 8px;
                padding: 8px 18px;
                font-weight: 700;
                font-size: 10pt;
            }

            QPushButton:hover {
                background-color: #eab308;
            }

            QPushButton:pressed {
                background-color: #ca8a04;
            }

            QPushButton:disabled {
                background-color: #292929;
                color: #4a4a4a;
            }

            QPushButton#GhostButton {
                background-color: transparent;
                color: #a1a1aa;
                border: 1px solid #2c2c2c;
                font-weight: 500;
            }

            QPushButton#GhostButton:hover {
                background-color: #1e1e1e;
                color: #f5f5f5;
                border-color: #3f3f3f;
            }

            QScrollBar:vertical {
                background: transparent;
                width: 6px;
                margin: 0px;
            }

            QScrollBar::handle:vertical {
                background: #2a2a2a;
                min-height: 32px;
                border-radius: 3px;
            }

            QScrollBar::handle:vertical:hover {
                background: #3f3f3f;
            }

            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0px;
            }

            QScrollBar:horizontal {
                height: 0px;
            }
            """
        )

    def open_chat(self, user, api_key):
        self.chat_page = ChatPage(user, api_key)
        self.chat_page.sign_out.connect(self.show_auth)

        if self.stack.count() == 1:
            self.stack.addWidget(self.chat_page)
        else:
            old = self.stack.widget(1)
            self.stack.removeWidget(old)
            old.deleteLater()
            self.stack.addWidget(self.chat_page)

        self.stack.setCurrentWidget(self.chat_page)

    def show_auth(self):
        self.stack.setCurrentWidget(self.auth_page)


def main():
    ensure_data_files()
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()