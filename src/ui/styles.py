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

    WARM_SURFACE = "#15130E"
    WARM_SURFACE_ALT = "#1D1A12"
    SOFT_BORDER = "#2E291B"
    SOFT_BORDER_HOVER = "#4A3D18"
    ACCENT_SOFT = "rgba(255, 204, 51, 0.12)"
    ACCENT_SOFT_QSS = "#2A2410"
    SHADOW = QColor(0, 0, 0, 130)


FONT_FAMILY = "Segoe UI"
FONT_SIZE_XS = 10
FONT_SIZE_SM = 11
FONT_SIZE_BASE = 13
FONT_SIZE_MD = 15
FONT_SIZE_LG = 20
FONT_SIZE_XL = 30

CHAT_MAX_WIDTH = 1080
CHAT_BUBBLE_MAX_WIDTH = 620
CHAT_SIDE_PADDING = 34
CHAT_TOP_PADDING = 22
CHAT_BOTTOM_PADDING = 20

BUBBLE_RADIUS = 16
BUBBLE_PADDING_Y = 12
BUBBLE_PADDING_X = 16
BUBBLE_LINE_HEIGHT = 1.45

CARD_RADIUS = 18
INPUT_RADIUS = 22
BUTTON_RADIUS = 13


PRIMARY_BTN = f"""
QPushButton {{
    background-color: {C.ACCENT};
    color: {C.USER_TEXT};
    border: 1px solid {C.ACCENT};
    border-radius: {BUTTON_RADIUS}px;
    padding: 11px 18px;
    font-size: {FONT_SIZE_BASE}px;
    font-weight: 700;
}}
QPushButton:hover {{
    background-color: {C.ACCENT_HOVER};
    border: 1px solid {C.ACCENT_HOVER};
}}
QPushButton:pressed {{
    background-color: #D6A900;
    border: 1px solid #D6A900;
    padding-top: 12px;
    padding-bottom: 10px;
}}
QPushButton:disabled {{
    background-color: #2A2A2A;
    color: #777777;
    border: 1px solid #333333;
}}
"""

SECONDARY_BTN = f"""
QPushButton {{
    background-color: {C.WARM_SURFACE_ALT};
    color: {C.TEXT};
    border: 1px solid {C.SOFT_BORDER};
    border-radius: {BUTTON_RADIUS}px;
    padding: 10px 16px;
    font-size: {FONT_SIZE_BASE}px;
    font-weight: 650;
}}
QPushButton:hover {{
    background-color: #242014;
    border: 1px solid {C.SOFT_BORDER_HOVER};
    color: {C.ACCENT};
}}
QPushButton:pressed {{
    background-color: #18150D;
    border: 1px solid {C.ACCENT};
}}
QPushButton:disabled {{
    background-color: #202020;
    color: #6D6D6D;
    border: 1px solid #303030;
}}
"""

GHOST_BTN = f"""
QPushButton {{
    background-color: transparent;
    color: {C.ACCENT};
    border: 1px solid {C.SOFT_BORDER_HOVER};
    border-radius: {BUTTON_RADIUS}px;
    padding: 10px 16px;
    font-size: {FONT_SIZE_BASE}px;
    font-weight: 650;
}}
QPushButton:hover {{
    background-color: {C.ACCENT_SOFT_QSS};
    border: 1px solid {C.ACCENT};
}}
QPushButton:pressed {{
    background-color: #332A0F;
    border: 1px solid {C.ACCENT_HOVER};
}}
QPushButton:disabled {{
    color: #666666;
    border: 1px solid #303030;
}}
"""

MODEL_BUTTON = f"""
QPushButton {{
    background-color: {C.WARM_SURFACE};
    color: {C.TEXT};
    border: 1px solid {C.SOFT_BORDER};
    border-radius: 16px;
    padding: 16px 18px;
    text-align: left;
    font-size: {FONT_SIZE_BASE}px;
    font-weight: 650;
}}
QPushButton:hover {{
    background-color: {C.WARM_SURFACE_ALT};
    border: 1px solid {C.SOFT_BORDER_HOVER};
}}
QPushButton:pressed {{
    background-color: #211C10;
    border: 1px solid {C.ACCENT};
}}
QPushButton:disabled {{
    background-color: #171717;
    color: #666666;
    border: 1px solid #2A2A2A;
}}
"""

MODEL_BUTTON_SELECTED = f"""
QPushButton {{
    background-color: {C.ACCENT_SOFT_QSS};
    color: {C.ACCENT};
    border: 1px solid {C.ACCENT};
    border-radius: 16px;
    padding: 16px 18px;
    text-align: left;
    font-size: {FONT_SIZE_BASE}px;
    font-weight: 750;
}}
QPushButton:hover {{
    background-color: #342B10;
    border: 1px solid {C.ACCENT_HOVER};
}}
QPushButton:pressed {{
    background-color: #403511;
    border: 1px solid {C.ACCENT_HOVER};
}}
"""

INPUT = f"""
QLineEdit, QTextEdit, QPlainTextEdit {{
    background-color: {C.INPUT_BG};
    color: {C.INPUT_TEXT};
    border: 1px solid {C.SOFT_BORDER};
    border-radius: 14px;
    padding: 11px 13px;
    font-size: {FONT_SIZE_BASE}px;
    selection-background-color: {C.ACCENT};
    selection-color: {C.USER_TEXT};
}}
QLineEdit:hover, QTextEdit:hover, QPlainTextEdit:hover {{
    border: 1px solid {C.SOFT_BORDER_HOVER};
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border: 1px solid {C.ACCENT};
    background-color: #151515;
}}
QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled {{
    background-color: #181818;
    color: #707070;
    border: 1px solid #2A2A2A;
}}
"""

CHAT_INPUT_CONTAINER = f"""
QFrame {{
    background-color: #12100B;
    border: 1px solid #3A321E;
    border-radius: {INPUT_RADIUS}px;
    padding: 6px;
}}
"""

COMBO = f"""
QComboBox {{
    background-color: {C.INPUT_BG};
    color: {C.INPUT_TEXT};
    border: 1px solid {C.SOFT_BORDER};
    border-radius: 13px;
    padding: 10px 12px;
    min-height: 22px;
    font-size: {FONT_SIZE_BASE}px;
}}
QComboBox:hover {{
    border: 1px solid {C.SOFT_BORDER_HOVER};
}}
QComboBox:focus {{
    border: 1px solid {C.ACCENT};
}}
QComboBox::drop-down {{
    border: none;
    width: 26px;
}}
QComboBox QAbstractItemView {{
    background-color: {C.WARM_SURFACE_ALT};
    color: {C.TEXT};
    border: 1px solid {C.SOFT_BORDER};
    selection-background-color: {C.ACCENT_SOFT_QSS};
    selection-color: {C.ACCENT};
    padding: 6px;
}}
"""

STATUS_LABEL = f"""
QLabel {{
    color: {C.STATUS_TEXT};
    font-size: {FONT_SIZE_SM}px;
}}
"""

PAGE_TITLE = f"""
QLabel {{
    color: {C.TEXT};
    font-size: {FONT_SIZE_XL}px;
    font-weight: 800;
    letter-spacing: -0.5px;
}}
"""

PAGE_SUBTITLE = f"""
QLabel {{
    color: {C.MUTED};
    font-size: {FONT_SIZE_BASE}px;
    line-height: 145%;
}}
"""

SECTION_CARD = f"""
QFrame {{
    background-color: {C.WARM_SURFACE};
    border: 1px solid {C.SOFT_BORDER};
    border-radius: {CARD_RADIUS}px;
}}
"""

CARD = SECTION_CARD

CHAT_PANEL = f"""
QFrame {{
    background-color: {C.BG};
    border: none;
}}
"""

USER_BUBBLE = f"""
QLabel {{
    background-color: #FFD34D;
    color: {C.USER_TEXT};
    border: none;
    border-radius: {BUBBLE_RADIUS}px;
    padding: {BUBBLE_PADDING_Y}px {BUBBLE_PADDING_X}px;
    font-size: {FONT_SIZE_BASE}px;
    font-weight: 500;
    line-height: {BUBBLE_LINE_HEIGHT};
}}
"""

ASSISTANT_BUBBLE = f"""
QLabel {{
    background-color: #1B1A16;
    color: {C.BOT_TEXT};
    border: 1px solid #2F2A1D;
    border-radius: {BUBBLE_RADIUS}px;
    padding: {BUBBLE_PADDING_Y}px {BUBBLE_PADDING_X}px;
    font-size: {FONT_SIZE_BASE}px;
    font-weight: 450;
    line-height: {BUBBLE_LINE_HEIGHT};
}}
"""

TYPING_INDICATOR_BUBBLE = f"""
QLabel {{
    background-color: {C.WARM_SURFACE_ALT};
    color: {C.MUTED};
    border: 1px solid {C.SOFT_BORDER};
    border-radius: 15px;
    padding: 9px 13px;
    font-size: {FONT_SIZE_SM}px;
    font-style: italic;
}}
"""

ERROR_BUBBLE = f"""
QLabel {{
    background-color: #1B1010;
    color: {C.DANGER};
    border: 1px solid {C.DANGER};
    border-radius: {BUBBLE_RADIUS}px;
    padding: {BUBBLE_PADDING_Y}px {BUBBLE_PADDING_X}px;
    font-size: {FONT_SIZE_BASE}px;
}}
"""

SCROLLBAR = f"""
QScrollBar:vertical {{
    background: transparent;
    width: 9px;
    margin: 6px 2px 6px 2px;
}}
QScrollBar::handle:vertical {{
    background: #3A3425;
    border-radius: 4px;
    min-height: 32px;
}}
QScrollBar::handle:vertical:hover {{
    background: #514723;
}}
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
        return USER_BUBBLE

    if role == "error":
        return ERROR_BUBBLE

    if role == "typing":
        return TYPING_INDICATOR_BUBBLE

    return ASSISTANT_BUBBLE


def make_shadow(
    widget: QWidget,
    blur_radius: float = 26.0,
    y_offset: float = 6.0,
    alpha: int = 120,
) -> QGraphicsDropShadowEffect:
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur_radius)
    effect.setOffset(0.0, y_offset)
    effect.setColor(QColor(0, 0, 0, alpha))
    return effect


def make_bubble_shadow(
    widget: QWidget,
    blur_radius: float = 18.0,
    y_offset: float = 3.0,
) -> QGraphicsDropShadowEffect:
    return make_shadow(
        widget,
        blur_radius=blur_radius,
        y_offset=y_offset,
        alpha=95,
    )


def make_card_shadow(
    widget: QWidget,
    blur_radius: float = 32.0,
    y_offset: float = 8.0,
) -> QGraphicsDropShadowEffect:
    return make_shadow(
        widget,
        blur_radius=blur_radius,
        y_offset=y_offset,
        alpha=115,
    )


def make_input_shadow(
    widget: QWidget,
    blur_radius: float = 24.0,
    y_offset: float = 5.0,
) -> QGraphicsDropShadowEffect:
    return make_shadow(
        widget,
        blur_radius=blur_radius,
        y_offset=y_offset,
        alpha=100,
    )


def apply_bubble_shadow(
    widget: QWidget,
    blur_radius: float = 18.0,
    y_offset: float = 3.0,
) -> None:
    widget.setGraphicsEffect(
        make_bubble_shadow(widget, blur_radius=blur_radius, y_offset=y_offset)
    )


def apply_card_shadow(
    widget: QWidget,
    blur_radius: float = 32.0,
    y_offset: float = 8.0,
) -> None:
    widget.setGraphicsEffect(
        make_card_shadow(widget, blur_radius=blur_radius, y_offset=y_offset)
    )


def apply_input_shadow(
    widget: QWidget,
    blur_radius: float = 24.0,
    y_offset: float = 5.0,
) -> None:
    widget.setGraphicsEffect(
        make_input_shadow(widget, blur_radius=blur_radius, y_offset=y_offset)
    )


_GLOBAL_QSS = f"""
QWidget {{
    background-color: {C.BG};
    color: {C.TEXT};
    font-family: '{FONT_FAMILY}';
    font-size: {FONT_SIZE_BASE}px;
}}

QMainWindow,
QStackedWidget,
QScrollArea,
QScrollArea > QWidget > QWidget {{
    background-color: {C.BG};
}}

QLabel {{
    color: {C.TEXT};
    background: transparent;
}}

QFrame {{
    background-color: transparent;
}}

{INPUT}
{COMBO}
{SCROLLBAR}

QPushButton {{
    min-height: 20px;
}}

QPushButton:focus,
QLineEdit:focus,
QTextEdit:focus,
QPlainTextEdit:focus,
QComboBox:focus {{
    outline: none;
}}

QToolTip {{
    background-color: {C.WARM_SURFACE_ALT};
    color: {C.TEXT};
    border: 1px solid {C.SOFT_BORDER};
    border-radius: 8px;
    padding: 7px 9px;
    font-size: {FONT_SIZE_SM}px;
}}
"""


def apply_app_style(app: QApplication) -> None:
    font = QFont(FONT_FAMILY, FONT_SIZE_BASE)
    app.setFont(font)

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(C.BG))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(C.TEXT))
    palette.setColor(QPalette.ColorRole.Base, QColor(C.INPUT_BG))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(C.WARM_SURFACE_ALT))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(C.WARM_SURFACE_ALT))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(C.TEXT))
    palette.setColor(QPalette.ColorRole.Text, QColor(C.TEXT))
    palette.setColor(QPalette.ColorRole.Button, QColor(C.WARM_SURFACE))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(C.TEXT))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(C.ACCENT))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(C.USER_TEXT))
    app.setPalette(palette)
    app.setStyleSheet(_GLOBAL_QSS)


def apply_global_styles(app: QApplication) -> None:
    apply_app_style(app)