"""Centralized PyQt6 styling for PetChat-2.0."""

from __future__ import annotations

from PyQt6.QtGui import QColor, QFont, QPalette
from PyQt6.QtWidgets import QApplication, QGraphicsDropShadowEffect, QWidget

from src.config import THEME_COLORS


class C:
    BG = THEME_COLORS["background"]
    SURFACE = THEME_COLORS["surface"]
    SURFACE_ALT = THEME_COLORS["surface_alt"]
    ACCENT = THEME_COLORS["accent"]
    ACCENT_HOVER = THEME_COLORS["accent_hover"]
    TEXT = THEME_COLORS["text"]
    MUTED = THEME_COLORS["muted_text"]
    DIVIDER = THEME_COLORS["divider"]
    USER_BUBBLE = THEME_COLORS["user_bubble"]
    USER_TEXT = THEME_COLORS["user_bubble_text"]
    BOT_BUBBLE = THEME_COLORS["bot_bubble"]
    BOT_TEXT = THEME_COLORS["bot_bubble_text"]
    INPUT_BG = THEME_COLORS["input_bg"]
    INPUT_TEXT = THEME_COLORS["input_text"]
    STATUS_TEXT = THEME_COLORS["status_text"]
    DANGER = THEME_COLORS["danger"]


FONT_FAMILY = "Segoe UI"
FONT_SIZE_SM = 11
FONT_SIZE_BASE = 13
FONT_SIZE_MD = 15
FONT_SIZE_LG = 20


PRIMARY_BTN = f"""
QPushButton {{
    background-color: {C.ACCENT};
    color: {C.USER_TEXT};
    border: none;
    border-radius: 10px;
    padding: 10px 16px;
    font-size: {FONT_SIZE_BASE}px;
    font-weight: 600;
}}
QPushButton:hover {{ background-color: {C.ACCENT_HOVER}; }}
QPushButton:pressed {{ background-color: {C.ACCENT_HOVER}; }}
QPushButton:disabled {{
    background-color: #343434;
    color: #777777;
}}
"""

GHOST_BTN = f"""
QPushButton {{
    background-color: transparent;
    color: {C.ACCENT};
    border: 1px solid {C.ACCENT};
    border-radius: 10px;
    padding: 10px 16px;
    font-size: {FONT_SIZE_BASE}px;
    font-weight: 600;
}}
QPushButton:hover {{ background-color: #181818; }}
QPushButton:pressed {{ background-color: #222222; }}
"""

INPUT = f"""
QLineEdit, QTextEdit, QPlainTextEdit {{
    background-color: {C.INPUT_BG};
    color: {C.INPUT_TEXT};
    border: 1px solid {C.DIVIDER};
    border-radius: 12px;
    padding: 10px 12px;
    selection-background-color: {C.ACCENT};
    selection-color: {C.USER_TEXT};
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border: 1px solid {C.ACCENT};
}}
"""

COMBO = f"""
QComboBox {{
    background-color: {C.INPUT_BG};
    color: {C.INPUT_TEXT};
    border: 1px solid {C.DIVIDER};
    border-radius: 12px;
    padding: 10px 12px;
    min-height: 18px;
}}
QComboBox:hover {{ border: 1px solid {C.ACCENT}; }}
QComboBox::drop-down {{
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
"""

STATUS_LABEL = f"""
QLabel {{
    color: {C.STATUS_TEXT};
    font-size: {FONT_SIZE_SM}px;
}}
"""

CARD = f"""
QFrame {{
    background-color: {C.SURFACE};
    border: 1px solid {C.DIVIDER};
    border-radius: 14px;
}}
"""

SCROLLBAR = f"""
QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 4px 0 4px 0;
}}
QScrollBar::handle:vertical {{
    background: #383838;
    border-radius: 4px;
    min-height: 28px;
}}
QScrollBar::handle:vertical:hover {{ background: #4a4a4a; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: transparent;
}}
QScrollBar:horizontal {{
    height: 0px;
}}
"""


def get_bubble_style(role: str) -> str:
    if role == "user":
        background = C.USER_BUBBLE
        foreground = C.USER_TEXT
        border = "none"
    elif role == "error":
        background = "#1B1010"
        foreground = C.DANGER
        border = f"1px solid {C.DANGER}"
    else:
        background = C.BOT_BUBBLE
        foreground = C.BOT_TEXT
        border = f"1px solid {C.DIVIDER}"

    return f"""
    QLabel {{
        background-color: {background};
        color: {foreground};
        border: {border};
        border-radius: 16px;
        padding: 10px 14px;
        font-size: {FONT_SIZE_BASE}px;
    }}
    """


def make_bubble_shadow(
    widget: QWidget,
    blur_radius: float = 18.0,
    y_offset: float = 2.0,
) -> QGraphicsDropShadowEffect:
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur_radius)
    effect.setOffset(0.0, y_offset)
    effect.setColor(QColor(0, 0, 0, 110))
    return effect


def apply_bubble_shadow(
    widget: QWidget,
    blur_radius: float = 18.0,
    y_offset: float = 2.0,
) -> None:
    widget.setGraphicsEffect(
        make_bubble_shadow(widget, blur_radius=blur_radius, y_offset=y_offset)
    )


_GLOBAL_QSS = f"""
QWidget {{
    background-color: {C.BG};
    color: {C.TEXT};
    font-family: '{FONT_FAMILY}';
    font-size: {FONT_SIZE_BASE}px;
}}
QMainWindow, QStackedWidget, QScrollArea, QScrollArea > QWidget > QWidget {{
    background-color: {C.BG};
}}
QLabel {{
    color: {C.TEXT};
    background: transparent;
}}
{INPUT}
{COMBO}
{SCROLLBAR}
QPushButton:focus, QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus {{
    outline: none;
}}
QToolTip {{
    background-color: {C.SURFACE_ALT};
    color: {C.TEXT};
    border: 1px solid {C.DIVIDER};
    padding: 6px 8px;
}}
"""


def apply_app_style(app: QApplication) -> None:
    font = QFont(FONT_FAMILY, FONT_SIZE_BASE)
    app.setFont(font)

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(C.BG))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(C.TEXT))
    palette.setColor(QPalette.ColorRole.Base, QColor(C.INPUT_BG))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(C.SURFACE_ALT))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(C.SURFACE_ALT))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(C.TEXT))
    palette.setColor(QPalette.ColorRole.Text, QColor(C.TEXT))
    palette.setColor(QPalette.ColorRole.Button, QColor(C.SURFACE))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(C.TEXT))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(C.ACCENT))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(C.USER_TEXT))
    app.setPalette(palette)
    app.setStyleSheet(_GLOBAL_QSS)


def apply_global_styles(app: QApplication) -> None:
    apply_app_style(app)