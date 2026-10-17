# -*- coding: utf-8 -*-
"""Koyu gri renk paleti (Octane / LightWave tarzı): pencere #3e3e40, alanlar daha koyu, düğmeler #58575c, vurgu açık mavi-gri.
Hem ana render penceresine hem Malzemeler penceresine uygulanır (apply)."""
import os

BG = "#3e3e40"          # pencere
PANEL = "#333335"       # koyu bar / liste başlığı
FIELD = "#2d2d30"       # metin/liste/sayı alanları
BTN = "#58575c"         # düğme, açılır liste
BTN_HOVER = "#67666c"
HEADER = "#4b4c50"
BORDER = "#26262a"
LINE = "#555559"
TEXT = "#d6d6d8"
TEXT_DIS = "#85858a"
ACCENT = "#5b7fa6"      # seçim
ACCENT_LIGHT = "#b5c5d5"  # işaretli kutu, sürgü tutamacı
PREVIEW_BG = "#2a2a2c"
PREVIEW_BORDER = "#6b7e92"

_ICONS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons").replace("\\", "/")


def stylesheet():
    return """
QDialog, QWidget#ybtroot {{ background-color: {BG}; }}
QWidget {{ color: {TEXT}; }}
QDialog, QScrollArea, QScrollArea > QWidget > QWidget {{ background-color: {BG}; }}
QLabel {{ background: transparent; }}
QToolTip {{ background-color: {BORDER}; color: {TEXT}; border: 1px solid {LINE}; padding: 3px; }}

QGroupBox {{ border: 1px solid {BORDER}; border-radius: 3px; margin-top: 18px; padding-top: 10px; background-color: {BG}; }}
QGroupBox::title {{ subcontrol-origin: margin; subcontrol-position: top left; left: 8px; padding: 0 4px; color: #e8e8ea; }}

QPushButton {{ background-color: {BTN}; border: 1px solid {BORDER}; border-radius: 3px; padding: 4px 10px; min-height: 16px; }}
QPushButton:hover {{ background-color: {BTN_HOVER}; }}
QPushButton:pressed {{ background-color: {ACCENT}; color: #ffffff; padding-top: 6px; padding-bottom: 2px; border-color: {ACCENT_LIGHT}; }}
QPushButton:checked {{ background-color: {ACCENT}; color: #ffffff; }}
QPushButton:disabled {{ background-color: {PANEL}; color: {TEXT_DIS}; border-color: {PANEL}; }}
QToolButton {{ background-color: transparent; border: none; padding: 2px 4px; color: #e8e8ea; font-weight: bold; }}
QToolButton:hover {{ color: #ffffff; }}

QCheckBox {{ spacing: 6px; background: transparent; }}
QCheckBox::indicator {{ width: 14px; height: 14px; background-color: {BTN}; border: 1px solid {BORDER}; border-radius: 2px; }}
QCheckBox::indicator:hover {{ background-color: {BTN_HOVER}; }}
QCheckBox::indicator:checked {{ background-color: {ACCENT_LIGHT}; image: url({ICONS}/check.png); }}
QCheckBox::indicator:disabled {{ background-color: {PANEL}; border-color: {PANEL}; }}
QCheckBox:disabled {{ color: {TEXT_DIS}; }}
QTreeWidget::indicator {{ width: 14px; height: 14px; background-color: {BTN}; border: 1px solid {BORDER}; border-radius: 2px; }}
QTreeWidget::indicator:checked {{ background-color: {ACCENT_LIGHT}; image: url({ICONS}/check.png); }}

QLineEdit, QPlainTextEdit, QTextEdit, QListWidget, QTreeWidget {{ background-color: {FIELD}; border: 1px solid {BORDER}; border-radius: 2px;
    selection-background-color: {ACCENT}; selection-color: #ffffff; }}
QListWidget::item:selected, QTreeWidget::item:selected {{ background-color: {ACCENT}; color: #ffffff; }}
QLineEdit, QSpinBox, QDoubleSpinBox {{ min-height: 20px; }}
QLineEdit:disabled {{ background-color: {PANEL}; color: {TEXT_DIS}; }}
QHeaderView::section {{ background-color: {HEADER}; color: {TEXT}; border: none; border-right: 1px solid {BORDER}; padding: 3px 6px; }}

QSpinBox, QDoubleSpinBox {{ background-color: {FIELD}; border: 1px solid {BORDER}; border-radius: 2px; padding: 2px 4px; padding-right: 18px;
    selection-background-color: {ACCENT}; }}
QSpinBox:disabled, QDoubleSpinBox:disabled {{ background-color: {PANEL}; color: {TEXT_DIS}; }}
QSpinBox::up-button, QDoubleSpinBox::up-button {{ subcontrol-origin: border; subcontrol-position: top right; width: 16px; background-color: {BTN};
    border-left: 1px solid {BORDER}; border-top-right-radius: 2px; }}
QSpinBox::down-button, QDoubleSpinBox::down-button {{ subcontrol-origin: border; subcontrol-position: bottom right; width: 16px; background-color: {BTN};
    border-left: 1px solid {BORDER}; border-bottom-right-radius: 2px; }}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover, QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{ background-color: {BTN_HOVER}; }}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{ image: url({ICONS}/up.png); width: 8px; height: 6px; }}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{ image: url({ICONS}/down.png); width: 8px; height: 6px; }}

QComboBox {{ background-color: {BTN}; border: 1px solid {BORDER}; border-radius: 3px; padding: 3px 8px; min-height: 16px; }}
QComboBox:hover {{ background-color: {BTN_HOVER}; }}
QComboBox:disabled {{ background-color: {PANEL}; color: {TEXT_DIS}; }}
QComboBox::drop-down {{ border: none; width: 20px; }}
QComboBox::down-arrow {{ image: url({ICONS}/down.png); width: 10px; height: 7px; }}
QComboBox QAbstractItemView {{ background-color: {FIELD}; border: 1px solid {BORDER}; selection-background-color: {ACCENT}; selection-color: #ffffff; outline: none; }}

QSlider::groove:horizontal {{ height: 4px; background: {BORDER}; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {ACCENT}; border-radius: 2px; }}
QSlider::handle:horizontal {{ background: {ACCENT_LIGHT}; width: 12px; height: 12px; margin: -5px 0; border-radius: 6px; }}
QSlider::handle:horizontal:disabled {{ background: {BTN}; }}
QSlider::groove:horizontal:disabled {{ background: {PANEL}; }}

QScrollBar:vertical {{ background: {PANEL}; width: 12px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {BTN}; min-height: 24px; border-radius: 4px; margin: 2px; }}
QScrollBar::handle:vertical:hover {{ background: {BTN_HOVER}; }}
QScrollBar:horizontal {{ background: {PANEL}; height: 12px; margin: 0; }}
QScrollBar::handle:horizontal {{ background: {BTN}; min-width: 24px; border-radius: 4px; margin: 2px; }}
QScrollBar::handle:horizontal:hover {{ background: {BTN_HOVER}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

QProgressBar {{ background-color: {BORDER}; border: 1px solid {BORDER}; border-radius: 3px; color: #ffffff; text-align: center; }}
QProgressBar::chunk {{ background-color: {ACCENT}; border-radius: 2px; }}
QSplitter::handle {{ background-color: {BORDER}; }}
QFrame[frameShape="4"], QFrame[frameShape="5"] {{ color: {LINE}; }}
""".format(BG=BG, PANEL=PANEL, FIELD=FIELD, BTN=BTN, BTN_HOVER=BTN_HOVER, HEADER=HEADER, BORDER=BORDER, LINE=LINE,
           TEXT=TEXT, TEXT_DIS=TEXT_DIS, ACCENT=ACCENT, ACCENT_LIGHT=ACCENT_LIGHT, ICONS=_ICONS)


def apply(widget):
    """Pencereye koyu paleti uygular (hata verirse sessizce varsayılan görünümde kalır)."""
    try:
        widget.setStyleSheet(stylesheet())
    except Exception:
        pass
