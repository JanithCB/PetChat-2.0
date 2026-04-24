"""
ui/styles.py — Centralised QSS palette and style helpers for PetChat-2.0.

All UI modules should import from here instead of hardcoding style strings.

Public API
----------
apply_global_styles(app)          — call once in main() after QApplication is created
get_bubble_style(role)            — "user" | "assistant" | "error"
PRIMARY_BTN / GHOST_BTN / INPUT   — QSS snippets for common widgets
C                                 — colour namespace (C.BG, C.ACCENT, …)
"""

from __future__ import annotations

from PyQt6.QtGui import QFont, QFontDatabase
from PyQt6.QtWidgets import QApplication

from petchat.config import THEME_COLORS as _T


# ---------------------------------------------------------------------------
# Colour namespace
# ---------------------------------------------------------------------------

class C:
    """Named colour constants — single source of truth for every QSS string."""

    BG            = _T["background"]          # #000000
    SURFACE       = "#0D0D0D"
    SURFACE_2     = "#111111"
    SURFACE_3     = "#1A1A1A"
    DIVIDER       = _T["divider"]             # #222222
    BORDER        = "#2E2E2E"

    ACCENT        = _T["accent"]              # #FFD54A
    ACCENT_HOVER  = "#FFE57A"
    ACCENT_ACTIVE = "#F0C030"

    USER_BUBBLE   = _T["user_bubble"]         # #FFD54A
    USER_TEXT     = _T["user_bubble_text"]    # #000000
    BOT_BUBBLE    = _T["bot_bubble"]          # #1A1A1A
    BOT_TEXT      = _T["bot_bubble_text"]     # #F0F0F0

    TEXT          = "#F0F0F0"
    TEXT_MUTED    = _T["status_text"]         # #888888
    TEXT_FAINT    = "#555555"

    INPUT_BG      = _T["input_bg"]            # #111111
    ERROR         = "#FF6B6B"
    SUCCESS       = "#6BCB77"


# ---------------------------------------------------------------------------
# Typography
# ---------------------------------------------------------------------------

FONT_FAMILY = "'Segoe UI', 'SF Pro Text', 'Helvetica Neue', Arial, sans-serif"

# Point sizes used across the app (keep to 4 levels).
FONT_SIZE_SM   = 11   # tiny labels, badges
FONT_SIZE_BASE = 13   # body / inputs
FONT_SIZE_MD   = 15   # buttons, headings
FONT_SIZE_LG   = 20   # page titles


# ---------------------------------------------------------------------------
# Reusable QSS snippets
# ---------------------------------------------------------------------------

# ---- Buttons ---------------------------------------------------------------

PRIMARY_BTN = f"""
    QPushButton {{
        background-color: {C.ACCENT};
        color: {C.USER_TEXT};
        border: none;
        border-radius: 6px;
        font-size: {FONT_SIZE_MD}px;
        font-weight: 600;
        letter-spacing: 0.4px;
        padding: 0 18px;
    }}
    QPushButton:hover  {{ background-color: {C.ACCENT_HOVER};  }}
    QPushButton:pressed {{ background-color: {C.ACCENT_ACTIVE}; }}
    QPushButton:disabled {{
        background-color: #333333;
        color: #666666;
    }}
"""

GHOST_BTN = f"""
    QPushButton {{
        background-color: transparent;
        color: {C.ACCENT};
        border: 1.5px solid {C.ACCENT};
        border-radius: 6px;
        font-size: {FONT_SIZE_BASE}px;
        font-weight: 600;
        padding: 0 14px;
    }}
    QPushButton:hover  {{ background-color: #1A1600; }}
    QPushButton:pressed {{ background-color: #2A2200; }}
    QPushButton:disabled {{
        color: {C.TEXT_FAINT};
        border-color: #333333;
    }}
"""

DANGER_BTN = f"""
    QPushButton {{
        background-color: transparent;
        color: {C.ERROR};
        border: 1px solid #333333;
        border-radius: 5px;
        font-size: {FONT_SIZE_SM + 1}px;
        padding: 0 10px;
    }}
    QPushButton:hover  {{ border-color: {C.ERROR}; }}
    QPushButton:pressed {{ background-color: #1A0000; }}
"""

# ---- Inputs ----------------------------------------------------------------

INPUT = f"""
    QLineEdit, QTextEdit {{
        background-color: {C.INPUT_BG};
        color: {C.TEXT};
        border: 1px solid {C.DIVIDER};
        border-radius: 6px;
        padding: 10px 12px;
        font-size: {FONT_SIZE_BASE}px;
        selection-background-color: {C.ACCENT};
        selection-color: #000000;
    }}
    QLineEdit:focus, QTextEdit:focus {{
        border: 1.5px solid {C.ACCENT};
    }}
    QLineEdit:disabled, QTextEdit:disabled {{
        background-color: #0A0A0A;
        color: {C.TEXT_FAINT};
    }}
"""

# ---- Field label -----------------------------------------------------------

FIELD_LABEL = f"""
    QLabel {{
        color: {C.TEXT_MUTED};
        font-size: {FONT_SIZE_SM}px;
        font-weight: 500;
    }}
"""

# ---- Card / panel ----------------------------------------------------------

CARD = f"""
    QFrame {{
        background-color: {C.SURFACE};
        border: 1px solid {C.DIVIDER};
        border-radius: 12px;
    }}
"""

# ---- Combo box -------------------------------------------------------------

COMBO = f"""
    QComboBox {{
        background-color: {C.INPUT_BG};
        color: {C.TEXT};
        border: 1px solid {C.DIVIDER};
        border-radius: 6px;
        padding: 8px 12px;
        font-size: {FONT_SIZE_BASE}px;
        selection-background-color: {C.ACCENT};
    }}
    QComboBox:focus {{ border: 1.5px solid {C.ACCENT}; }}
    QComboBox::drop-down {{ border: none; width: 24px; }}
    QComboBox QAbstractItemView {{
        background-color: {C.SURFACE_3};
        color: {C.TEXT};
        selection-background-color: {C.ACCENT};
        selection-color: #000000;
        border: 1px solid {C.DIVIDER};
        outline: none;
    }}
"""

# ---- Scrollbar (vertical only) ---------------------------------------------

SCROLLBAR = f"""
    QScrollBar:vertical {{
        background: {C.BG};
        width: 6px;
        border-radius: 3px;
    }}
    QScrollBar::handle:vertical {{
        background: #333333;
        border-radius: 3px;
        min-height: 30px;
    }}
    QScrollBar::handle:vertical:hover {{ background: {C.ACCENT}; }}
    QScrollBar::add-line:vertical,
    QScrollBar::sub-line:vertical {{ height: 0px; }}
    QScrollBar:horizontal {{ height: 0px; }}
"""

# ---- Status / error labels -------------------------------------------------

STATUS_LABEL = f"""
    QLabel {{
        color: {C.TEXT_MUTED};
        font-size: {FONT_SIZE_SM}px;
        font-style: italic;
    }}
"""

ERROR_LABEL = f"""
    QLabel {{
        color: {C.ERROR};
        font-size: {FONT_SIZE_SM}px;
    }}
"""


# ---------------------------------------------------------------------------
# Chat bubble styles
# ---------------------------------------------------------------------------

def get_bubble_style(role: str) -> str:
    """
    Return a QSS string for a chat bubble QLabel.

    Parameters
    ----------
    role : "user" | "assistant" | "error"
    """
    if role == "user":
        bg, fg  = C.USER_BUBBLE, C.USER_TEXT
        radius  = "18px 18px 4px 18px"
        border  = "none"
    elif role == "error":
        bg, fg  = "#1A0000", C.ERROR
        radius  = "18px 18px 18px 4px"
        border  = f"1px solid {C.ERROR}"
    else:  # "assistant"
        bg, fg  = C.BOT_BUBBLE, C.BOT_TEXT
        radius  = "18px 18px 18px 4px"
        border  = f"1px solid {C.DIVIDER}"

    return f"""
        QLabel {{
            background-color: {bg};
            color: {fg};
            border: {border};
            border-radius: {radius};
            padding: 10px 14px;
            font-size: {FONT_SIZE_BASE + 1}px;
            line-height: 1.5;
        }}
    """


# ---------------------------------------------------------------------------
# Global application stylesheet
# ---------------------------------------------------------------------------

_GLOBAL_QSS = f"""
    /* ── Base ── */
    QWidget {{
        background-color: {C.BG};
        color: {C.TEXT};
        font-family: {FONT_FAMILY};
        font-size: {FONT_SIZE_BASE}px;
    }}

    /* ── Inputs ── */
    {INPUT}

    /* ── Combo ── */
    {COMBO}

    /* ── Scrollbars ── */
    {SCROLLBAR}

    /* ── Tooltip ── */
    QToolTip {{
        background-color: {C.SURFACE_3};
        color: {C.TEXT};
        border: 1px solid {C.BORDER};
        border-radius: 4px;
        padding: 4px 8px;
        font-size: {FONT_SIZE_SM}px;
    }}

    /* ── Menu ── */
    QMenu {{
        background-color: {C.SURFACE_2};
        color: {C.TEXT};
        border: 1px solid {C.DIVIDER};
        border-radius: 6px;
        padding: 4px 0;
    }}
    QMenu::item {{ padding: 6px 24px; }}
    QMenu::item:selected {{ background-color: {C.ACCENT}; color: #000000; }}
    QMenu::separator {{
        height: 1px;
        background: {C.DIVIDER};
        margin: 4px 0;
    }}

    /* ── Message box ── */
    QMessageBox {{
        background-color: {C.SURFACE};
    }}
    QMessageBox QLabel {{
        color: {C.TEXT};
        font-size: {FONT_SIZE_BASE}px;
    }}
    QMessageBox QPushButton {{
        {PRIMARY_BTN}
        min-width: 80px;
        min-height: 32px;
    }}
"""


def apply_global_styles(app: QApplication) -> None:
    """
    Apply the global QSS palette to a QApplication instance.
    Call once in main(), right after QApplication is created.

    Example
    -------
    app = QApplication(sys.argv)
    apply_global_styles(app)
    """
    # Set a clean default font (system-native if custom fonts aren't bundled).
    font = QFont()
    font.setFamily("Segoe UI")
    font.setPointSize(FONT_SIZE_BASE)
    font.setHintingPreference(QFont.HintingPreference.PreferFullHinting)
    app.setFont(font)

    app.setStyleSheet(_GLOBAL_QSS)
