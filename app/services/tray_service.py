"""System tray integration."""

from __future__ import annotations

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QAction, QColor, QIcon, QLinearGradient, QPainter, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon, QWidget


class TrayService(QObject):
    """Create and manage the system tray icon and menu."""

    show_requested = Signal()
    hide_requested = Signal()
    next_requested = Signal()
    previous_requested = Signal()
    undo_requested = Signal()
    quit_requested = Signal()

    def __init__(self, parent_window: QWidget) -> None:
        super().__init__(parent_window)
        self.parent_window = parent_window
        self.tray_icon = QSystemTrayIcon(self._build_icon(), self)
        self.tray_icon.setToolTip("ParaComment")
        self.tray_icon.activated.connect(self._handle_activated)
        self._menu = QMenu()
        self._show_action = QAction("显示窗口", self)
        self._show_action.triggered.connect(self._toggle_window)
        self._next_action = QAction("下一段并粘贴", self)
        self._next_action.triggered.connect(self.next_requested.emit)
        self._previous_action = QAction("上一段", self)
        self._previous_action.triggered.connect(self.previous_requested.emit)
        self._undo_action = QAction("撤销上一次工具粘贴", self)
        self._undo_action.triggered.connect(self.undo_requested.emit)
        self._quit_action = QAction("退出", self)
        self._quit_action.triggered.connect(self.quit_requested.emit)

        self._menu.addAction(self._show_action)
        self._menu.addSeparator()
        self._menu.addAction(self._next_action)
        self._menu.addAction(self._previous_action)
        self._menu.addAction(self._undo_action)
        self._menu.addSeparator()
        self._menu.addAction(self._quit_action)
        self.tray_icon.setContextMenu(self._menu)

    def show(self) -> None:
        self.tray_icon.show()

    def show_message(self, title: str, message: str) -> None:
        self.tray_icon.showMessage(title, message, QSystemTrayIcon.Information, 3000)

    def update_window_action(self, visible: bool) -> None:
        self._show_action.setText("隐藏窗口" if visible else "显示窗口")

    def _toggle_window(self) -> None:
        if self.parent_window.isVisible():
            self.hide_requested.emit()
        else:
            self.show_requested.emit()

    def _handle_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in {QSystemTrayIcon.DoubleClick, QSystemTrayIcon.Trigger}:
            self._toggle_window()

    @staticmethod
    def _build_icon() -> QIcon:
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        gradient = QLinearGradient(0, 0, 64, 64)
        gradient.setColorAt(0.0, QColor("#0f766e"))
        gradient.setColorAt(1.0, QColor("#0f172a"))
        painter.setBrush(gradient)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(4, 4, 56, 56, 14, 14)
        painter.setPen(QColor("#fef3c7"))
        font = painter.font()
        font.setBold(True)
        font.setPointSize(28)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignCenter, "P")
        painter.end()
        return QIcon(pixmap)
