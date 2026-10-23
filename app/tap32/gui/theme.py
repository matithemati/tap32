# ruff: noqa: E501
"""Motyw aplikacji: tokeny kolorów (jasny/ciemny), arkusz QSS i ikony liniowe (SVG)."""

from __future__ import annotations

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPalette, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication

LIGHT = {
    "bg": "#F4F4F6",
    "surface": "#FFFFFF",
    "surface2": "#FCFCFD",
    "soft": "#F6F6F8",
    "hover": "#EDEDF0",
    "border": "#E6E6EA",
    "border2": "#ECECEF",
    "text": "#111113",
    "sub": "#55555D",
    "muted": "#6B6B73",
    "faint": "#9A9AA2",
    "accent": "#6D5BD0",
    "accent_soft": "#E6E3F8",
    "accent_text": "#2E2380",
    "primary": "#111113",
    "primary_hover": "#2A2A2E",
    "on_primary": "#FFFFFF",
    "danger": "#B42318",
    "ok": "#16A34A",
    "ok_soft": "#E7F6EC",
    "ok_text": "#166534",
    "warn_soft": "#FFF6E5",
    "warn_border": "#F6DFAE",
    "warn_text": "#7A4A00",
    "info_soft": "#EEF4FF",
    "info_border": "#D3E0FB",
    "info_text": "#1E3A8A",
    "switch_off": "#D4D4DA",
    "knob_ring": "#EDEDF0",
    "knob_tick": "#B9B9C0",
    "knob_face": "#FFFFFF",
    "knob_inner": "#F7F7F9",
}

DARK = {
    "bg": "#0F0F11",
    "surface": "#18181B",
    "surface2": "#1B1B1F",
    "soft": "#202024",
    "hover": "#26262B",
    "border": "#2A2A2F",
    "border2": "#26262B",
    "text": "#EDEDEF",
    "sub": "#B4B4BC",
    "muted": "#9A9AA3",
    "faint": "#6E6E77",
    "accent": "#9D8FF0",
    "accent_soft": "#2C2650",
    "accent_text": "#DCD6FF",
    "primary": "#EDEDEF",
    "primary_hover": "#FFFFFF",
    "on_primary": "#111113",
    "danger": "#F97066",
    "ok": "#22C55E",
    "ok_soft": "#14301F",
    "ok_text": "#86EFAC",
    "warn_soft": "#33270F",
    "warn_border": "#5A4317",
    "warn_text": "#F5C46B",
    "info_soft": "#16213A",
    "info_border": "#24365E",
    "info_text": "#A9C2FF",
    "switch_off": "#3A3A41",
    "knob_ring": "#26262B",
    "knob_tick": "#4A4A52",
    "knob_face": "#202024",
    "knob_inner": "#1B1B1F",
}

_tokens: dict[str, str] = dict(LIGHT)
_dark = False


def tokens() -> dict[str, str]:
    return _tokens


def color(name: str) -> QColor:
    return QColor(_tokens[name])


def is_dark() -> bool:
    return _dark


QSS = """
* {{ font-family: "Segoe UI Variable Text", "Segoe UI", sans-serif; font-size: 10pt; }}
QMainWindow, QWidget#root {{ background: {bg}; }}
QWidget {{ color: {text}; }}
QToolTip {{ background: {surface}; color: {text}; border: 1px solid {border}; padding: 4px 6px; }}

QFrame#card, QWidget#card {{ background: {surface}; border: 1px solid {border}; border-radius: 14px; }}
QFrame#main {{ background: {surface}; border: 1px solid {border}; border-radius: 16px; }}
QFrame#devicePane {{ background: {surface2}; border: none; border-top-left-radius: 14px; border-bottom-left-radius: 14px; }}
QFrame#inspector {{ background: transparent; border: none; border-left: 1px solid {border2}; }}
QFrame#soft {{ background: {soft}; border: 1px solid {border2}; border-radius: 12px; }}
QFrame#outlined {{ background: transparent; border: 1px solid {border2}; border-radius: 12px; }}
QFrame#hline {{ background: {border}; border: none; max-height: 1px; min-height: 1px; }}
QFrame#oled {{ background: #06090D; border-radius: 12px; border: none; }}
QFrame#bannerWarn {{ background: {warn_soft}; border: 1px solid {warn_border}; border-radius: 10px; }}
QFrame#bannerWarn QLabel {{ color: {warn_text}; }}
QFrame#bannerInfo {{ background: {info_soft}; border: 1px solid {info_border}; border-radius: 10px; }}
QFrame#bannerInfo QLabel {{ color: {info_text}; }}
QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; border: none; }}
QStackedWidget {{ background: transparent; }}

QLabel {{ background: transparent; }}
QLabel#h1 {{ font-size: 19pt; font-weight: 700; }}
QLabel#h2 {{ font-size: 13.5pt; font-weight: 700; }}
QLabel#brand {{ font-size: 11.5pt; font-weight: 700; }}
QLabel#kicker {{ font-size: 8pt; font-weight: 600; color: {muted}; letter-spacing: 1px; }}
QLabel#section {{ font-size: 8pt; font-weight: 700; color: {sub}; letter-spacing: 1px; }}
QLabel#muted, QLabel#hint {{ color: {muted}; }}
QLabel#lbl {{ color: {sub}; font-size: 9pt; font-weight: 600; }}
QLabel#strong {{ font-weight: 600; }}
QLabel#error {{ color: {danger}; }}
QLabel#crumb {{ color: {sub}; font-size: 9pt; }}
QLabel#crumbCur {{ color: {text}; background: {soft}; border-radius: 6px; padding: 2px 8px; font-size: 9pt; font-weight: 500; }}
QLabel#chipOk {{ background: {ok_soft}; color: {ok_text}; border-radius: 11px; padding: 2px 10px; font-size: 8.5pt; font-weight: 600; }}
QLabel#chip {{ background: {soft}; color: {sub}; border-radius: 11px; padding: 2px 10px; font-size: 8.5pt; font-weight: 600; }}
QLabel#oledPreview {{ background: #06090D; color: #7CC4FF; border-radius: 4px; padding: 1px 8px; font-family: Consolas, monospace; }}
QLabel#badge {{ border-radius: 11px; font-weight: 700; font-size: 10pt; }}

QPushButton, QToolButton {{
    background: {surface}; color: {text}; border: 1px solid {border};
    border-radius: 8px; padding: 6px 12px; font-weight: 500; min-height: 20px;
}}
QPushButton:hover, QToolButton:hover {{ background: {soft}; }}
QPushButton:pressed, QToolButton:pressed {{ background: {hover}; }}
QPushButton:disabled, QToolButton:disabled {{ color: {faint}; }}
QPushButton:focus, QToolButton:focus {{ border-color: {accent}; }}
QPushButton[primary="true"] {{ background: {primary}; color: {on_primary}; border-color: {primary}; }}
QPushButton[primary="true"]:hover {{ background: {primary_hover}; }}
QPushButton[primary="true"]:disabled {{ background: {hover}; color: {sub}; border-color: {hover}; }}
QPushButton[ghost="true"], QToolButton[ghost="true"] {{ background: transparent; border-color: transparent; padding: 4px; }}
QPushButton[ghost="true"]:hover, QToolButton[ghost="true"]:hover {{ background: {hover}; }}
QPushButton[danger="true"] {{ color: {danger}; }}
QToolButton::menu-indicator {{ image: none; width: 0; }}
QPushButton:checked[record="true"] {{ background: {primary}; color: {on_primary}; border-color: {primary}; }}

QPushButton[nav="true"] {{
    background: transparent; border: 1px solid transparent; border-radius: 8px;
    text-align: left; padding: 7px 10px; font-size: 10.5pt; color: {sub};
}}
QPushButton[nav="true"]:hover {{ background: {hover}; }}
QPushButton[nav="true"]:checked {{ background: {surface}; border-color: {border}; color: {text}; font-weight: 600; }}

QFrame#seg {{ background: {hover}; border-radius: 9px; border: none; }}
QPushButton[seg="true"] {{
    background: transparent; border: 1px solid transparent; border-radius: 7px;
    padding: 4px 10px; color: {sub}; font-size: 9.5pt; min-height: 18px;
}}
QPushButton[seg="true"]:hover {{ color: {text}; }}
QPushButton[seg="true"]:checked {{ background: {surface}; color: {text}; border-color: {border}; }}

QPushButton[stab="true"] {{
    background: transparent; border: none; border-radius: 8px; text-align: left;
    padding: 8px 12px; font-size: 10.5pt; color: {sub};
}}
QPushButton[stab="true"]:hover {{ background: {soft}; }}
QPushButton[stab="true"]:checked {{ background: {accent_soft}; color: {accent_text}; font-weight: 600; }}

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit {{
    background: {surface}; border: 1px solid {border}; border-radius: 8px;
    padding: 6px 9px; selection-background-color: {accent}; selection-color: #ffffff;
    min-height: 20px;
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QPlainTextEdit:focus {{
    border: 1px solid {accent};
}}
QLineEdit:disabled, QSpinBox:disabled, QComboBox:disabled {{ color: {faint}; background: {soft}; }}
QPlainTextEdit {{ font-family: Consolas, "Cascadia Mono", monospace; font-size: 9.5pt; }}
QPlainTextEdit#log {{ border: none; border-radius: 0; background: {surface}; padding: 8px 12px; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{
    background: {surface}; border: 1px solid {border}; border-radius: 8px; padding: 4px;
    selection-background-color: {soft}; selection-color: {text}; outline: none;
}}
QSpinBox::up-button, QSpinBox::down-button, QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    border: none; width: 16px;
}}

QListWidget {{ background: transparent; border: none; outline: none; }}
QListWidget::item {{ border-radius: 8px; padding: 7px 10px; margin: 1px 0; color: {sub}; }}
QListWidget::item:hover {{ background: {hover}; }}
QListWidget::item:selected {{ background: {accent_soft}; color: {accent_text}; }}
QListWidget#boxed {{ background: {surface}; border: 1px solid {border}; border-radius: 10px; padding: 4px; }}
QListWidget#boxed::item {{ color: {text}; padding: 6px 8px; }}

QTabWidget::pane {{ border: none; border-top: 1px solid {border2}; top: -1px; }}
QTabBar {{ qproperty-drawBase: 0; }}
QTabBar::tab {{
    background: transparent; border: none; border-bottom: 2px solid transparent;
    padding: 7px 2px; margin-right: 14px; color: {muted}; font-weight: 500;
}}
QTabBar::tab:selected {{ color: {text}; border-bottom-color: {text}; }}
QTabBar::tab:hover {{ color: {text}; }}

QTableWidget {{
    background: {surface}; border: 1px solid {border2}; border-radius: 12px;
    gridline-color: {border2}; outline: none;
}}
QTableWidget::item {{ padding: 4px; }}
QHeaderView::section {{
    background: {surface2}; color: {sub}; border: none; border-bottom: 1px solid {border2};
    padding: 8px 10px; font-weight: 600; font-size: 9pt;
}}

QSlider::groove:horizontal {{ height: 4px; background: {hover}; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {primary}; border-radius: 2px; }}
QSlider::handle:horizontal {{
    background: {surface}; border: 1px solid {border}; width: 16px; height: 16px;
    margin: -7px 0; border-radius: 8px;
}}

QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 4px; border: 1px solid {border}; background: {surface}; }}
QCheckBox::indicator:checked {{ background: {primary}; border-color: {primary}; }}

QMenu {{ background: {surface}; border: 1px solid {border}; border-radius: 12px; padding: 6px; }}
QMenu::item {{ padding: 7px 28px 7px 12px; border-radius: 7px; color: {text}; }}
QMenu::item:selected {{ background: {soft}; }}
QMenu::item:disabled {{ color: {faint}; }}
QMenu::separator {{ height: 1px; background: {border2}; margin: 5px 6px; }}
QMenu::icon {{ padding-left: 8px; }}
QMenu::indicator {{ width: 14px; height: 14px; left: 6px; }}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {border}; border-radius: 4px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {faint}; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {border}; border-radius: 4px; min-width: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{ background: none; border: none; width: 0; height: 0; }}

QDialog {{ background: {surface}; }}
QMessageBox {{ background: {surface}; }}
"""


def stylesheet() -> str:
    return QSS.format(**_tokens)


def palette() -> QPalette:
    t = _tokens
    p = QPalette()
    roles = {
        QPalette.ColorRole.Window: t["bg"],
        QPalette.ColorRole.WindowText: t["text"],
        QPalette.ColorRole.Base: t["surface"],
        QPalette.ColorRole.AlternateBase: t["soft"],
        QPalette.ColorRole.ToolTipBase: t["surface"],
        QPalette.ColorRole.ToolTipText: t["text"],
        QPalette.ColorRole.Text: t["text"],
        QPalette.ColorRole.Button: t["surface"],
        QPalette.ColorRole.ButtonText: t["text"],
        QPalette.ColorRole.BrightText: t["danger"],
        QPalette.ColorRole.Highlight: t["accent"],
        QPalette.ColorRole.HighlightedText: "#ffffff",
        QPalette.ColorRole.Link: t["accent"],
        QPalette.ColorRole.Mid: t["muted"],
        QPalette.ColorRole.PlaceholderText: t["faint"],
    }
    for role, value in roles.items():
        p.setColor(role, QColor(value))
    for role in (
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
        QPalette.ColorRole.WindowText,
    ):
        p.setColor(QPalette.ColorGroup.Disabled, role, QColor(t["faint"]))
    return p


def apply_theme(app: QApplication, theme: str) -> None:
    """Motyw jasny/ciemny; „system” – według ustawień Windows."""
    global _dark
    app.setStyle("Fusion")
    hints = app.styleHints()
    if theme == "system":
        if hasattr(hints, "unsetColorScheme"):
            hints.unsetColorScheme()
        dark = hints.colorScheme() == Qt.ColorScheme.Dark
    else:
        dark = theme == "dark"
        if hasattr(hints, "setColorScheme"):
            hints.setColorScheme(Qt.ColorScheme.Dark if dark else Qt.ColorScheme.Light)
    _dark = dark
    _tokens.clear()
    _tokens.update(DARK if dark else LIGHT)
    font = QFont("Segoe UI", 10)
    app.setFont(font)
    app.setPalette(palette())
    app.setStyleSheet(stylesheet())
    for widget in app.allWidgets():
        widget.update()


# --------------------------------------------------------------------------- ikony

_PATHS = {
    "dots-v": '<circle cx="12" cy="5" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="12" cy="19" r="1"/>',
    "dots-h": '<circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/>',
    "grid": '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/>'
    '<rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
    "list": '<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>',
    "sliders": '<path d="M20 7h-9M14 17H5"/><circle cx="17" cy="17" r="3"/><circle cx="7" cy="7" r="3"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "import": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/>',
    "export": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M17 8l-5-5-5 5M12 3v12"/>',
    "window": '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 15h18"/>',
    "info": '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/>',
    "power": '<path d="M12 2v10M18.4 6.6a9 9 0 1 1-12.8 0"/>',
    "flask": '<path d="M9 2v6L4 18a2 2 0 0 0 2 3h12a2 2 0 0 0 2-3L15 8V2M8 2h8"/>',
    "refresh": '<path d="M21 12a9 9 0 1 1-3-6.7L21 8M21 3v5h-5"/>',
    "download": '<path d="M4 14.9V20h16v-5.1M12 4v11M7 10l5 5 5-5"/>',
    "plug": '<path d="M12 22v-5M9 8V2M15 8V2M18 8v5a4 4 0 0 1-4 4h-4a4 4 0 0 1-4-4V8z"/>',
    "globe": '<circle cx="12" cy="12" r="10"/><path d="M2 12h20M12 2a15 15 0 0 1 0 20 15 15 0 0 1 0-20"/>',
    "home": '<path d="M3 10.5 12 3l9 7.5V21H3z"/>',
    "chevron": '<path d="m9 18 6-6-6-6"/>',
    "x": '<path d="M18 6 6 18M6 6l12 12"/>',
    "pencil": '<path d="M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/>',
    "copy": '<rect x="8" y="8" width="13" height="13" rx="2"/><path d="M16 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h3"/>',
    "trash": '<path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6"/>',
    "check": '<path d="M20 6 9 17l-5-5"/>',
    "play": '<path d="m7 4 13 8-13 8z"/>',
    "pause": '<path d="M6 4h4v16H6zM14 4h4v16h-4z"/>',
}


def icon(name: str, color_name: str = "text", size: int = 16) -> QIcon:
    """Ikona liniowa (styl Lucide) w kolorze tokenu motywu."""
    stroke = _tokens.get(color_name, color_name)
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        f'stroke="{stroke}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        f"{_PATHS[name]}</svg>"
    )
    renderer = QSvgRenderer(QByteArray(svg.encode()))
    result = QIcon()
    for scale in (1, 2):
        pix = QPixmap(size * scale, size * scale)
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        renderer.render(p, QRectF(0, 0, size * scale, size * scale))
        p.end()
        pix.setDevicePixelRatio(scale)
        result.addPixmap(pix)
    return result
