"""Application-wide styling helpers."""

from __future__ import annotations

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

APP_STYLESHEET = """
QWidget {
    background: #f6f1e7;
    color: #10233f;
    font-family: "Microsoft YaHei UI", "Segoe UI Variable Text", "Segoe UI";
    font-size: 13px;
}

QWidget#RootWindow,
QWidget#RootContent,
QScrollArea#AppScrollArea {
    background: #f6f1e7;
}

QScrollArea#AppScrollArea {
    border: none;
}

QWidget#HeaderCard,
QGroupBox#Card {
    background: #fffdf8;
    border: 1px solid #e8dbc4;
    border-radius: 18px;
}

QGroupBox#Card {
    margin-top: 16px;
    padding-top: 18px;
}

QGroupBox#Card::title {
    subcontrol-origin: margin;
    left: 16px;
    padding: 0 8px;
    color: #0f766e;
    font-weight: 700;
    background: #fffdf8;
}

QLabel#TitleLabel {
    font-size: 28px;
    font-weight: 800;
    color: #10233f;
    background: transparent;
}

QLabel#SubtitleLabel {
    color: #52627a;
    font-size: 13px;
    background: transparent;
}

QLabel#AccentChip {
    background: #ecfccb;
    color: #3f6212;
    border-radius: 12px;
    padding: 4px 12px;
    font-size: 12px;
    font-weight: 700;
}

QLabel#MetricLabel {
    color: #64748b;
    font-size: 12px;
    background: transparent;
}

QLabel#MetricValue {
    color: #10233f;
    font-size: 19px;
    font-weight: 800;
    background: transparent;
}

QLabel#PathHint {
    color: #7b8798;
    font-size: 12px;
    background: transparent;
}

QLabel#HotkeyName {
    color: #10233f;
    font-weight: 700;
    background: transparent;
}

QLabel#HintText {
    color: #52627a;
    background: transparent;
}

QLabel#StatusLabel {
    background: #fff7ed;
    color: #9a3412;
    border: 1px solid #fed7aa;
    border-radius: 14px;
    padding: 10px 12px;
    font-weight: 600;
}

QLineEdit,
QSpinBox {
    background: #fffaf0;
    color: #10233f;
    border: 1px solid #dccfb7;
    border-radius: 12px;
    padding: 0 12px;
    min-height: 24px;
}

QSpinBox::up-button,
QSpinBox::down-button {
    width: 18px;
    border: none;
    background: transparent;
}

QLineEdit#HotkeyEditor {
    font-family: "Cascadia Code", "Consolas";
    font-size: 12px;
    font-weight: 700;
}

QLineEdit:focus,
QSpinBox:focus {
    border-color: #0f766e;
    background: #fffdf8;
}

QPushButton {
    background: #fffaf0;
    color: #10233f;
    border: 1px solid #dccfb7;
    border-radius: 12px;
    padding: 0 16px;
    min-height: 24px;
    font-weight: 700;
}

QPushButton:hover {
    background: #fef8ef;
    border-color: #0f766e;
}

QPushButton:pressed {
    background: #f2eadd;
}

QPushButton#PrimaryButton {
    background: #0f766e;
    color: white;
    border: 1px solid #0f766e;
}

QPushButton#PrimaryButton:hover {
    background: #115e59;
    border-color: #115e59;
}

QPushButton#DangerButton {
    background: #fff1f2;
    color: #9f1239;
    border: 1px solid #fecdd3;
}

QPushButton#DangerButton:hover {
    background: #ffe4e6;
    border-color: #fb7185;
}

QRadioButton::indicator {
    width: 0px;
    height: 0px;
}

QRadioButton {
    background: #fffaf0;
    color: #10233f;
    border: 1px solid #dccfb7;
    border-radius: 12px;
    padding: 0 18px;
    min-height: 24px;
    font-weight: 800;
}

QRadioButton:hover {
    border-color: #0f766e;
}

QRadioButton:checked {
    background: #10233f;
    color: white;
    border-color: #10233f;
}

QPlainTextEdit {
    background: #0f172a;
    color: #f8fafc;
    border: 1px solid #1e293b;
    border-radius: 16px;
    padding: 14px;
    font-family: "Cascadia Code", "Consolas";
    font-size: 12.5px;
    selection-background-color: #0f766e;
}

QScrollBar:vertical {
    background: transparent;
    width: 12px;
    margin: 6px 0;
}

QScrollBar::handle:vertical {
    background: #cbd5e1;
    border-radius: 6px;
    min-height: 24px;
}

QScrollBar::handle:vertical:hover {
    background: #94a3b8;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {
    background: transparent;
    height: 0px;
}
"""


def apply_app_theme(app: QApplication) -> None:
    """Apply a consistent visual theme to the application."""
    app.setFont(QFont("Microsoft YaHei UI", 10))
    app.setStyleSheet(APP_STYLESHEET)
