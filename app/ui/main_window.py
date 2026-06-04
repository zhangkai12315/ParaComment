"""Main application window."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.models import HotkeySpec, OutputMode, PasteMode, SessionState
from app.services.text_loader import format_paragraph
from app.ui.hotkey_edit import HotkeyEdit


class MainWindow(QWidget):
    """Minimal GUI for file selection, progress display, and controls."""

    file_selected = Signal(str)
    comment_style_changed = Signal(str)
    output_mode_changed = Signal(str)
    paste_mode_changed = Signal(str)
    smart_chunk_length_changed = Signal(int)
    restore_clipboard_changed = Signal(bool)
    recent_file_selected = Signal(str)
    chapter_selected = Signal(int)
    hotkeys_apply_requested = Signal(object)
    hotkeys_reset_requested = Signal()
    hotkey_capture_started = Signal()
    hotkey_capture_finished = Signal()
    next_requested = Signal()
    previous_requested = Signal()
    undo_requested = Signal()
    minimize_requested = Signal()

    def __init__(self, hotkey_specs: list[HotkeySpec]) -> None:
        super().__init__()
        self._allow_close = False
        self._file_path: Path | None = None
        self._hotkey_specs: list[HotkeySpec] = list(hotkey_specs)
        self._hotkey_inputs: dict[str, HotkeyEdit] = {}
        self.setObjectName("RootWindow")
        self.setWindowTitle("ParaComment")
        self.resize(920, 860)
        self.setMinimumSize(780, 680)
        self._build_ui()
        self.set_hotkeys(hotkey_specs)

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        scroll_area = QScrollArea(self)
        scroll_area.setObjectName("AppScrollArea")
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        root_layout.addWidget(scroll_area)

        content = QWidget()
        content.setObjectName("RootContent")
        scroll_area.setWidget(content)

        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        header_card = QWidget()
        header_card.setObjectName("HeaderCard")
        header_layout = QVBoxLayout(header_card)
        header_layout.setContentsMargins(20, 18, 20, 18)
        header_layout.setSpacing(8)

        title_label = QLabel("ParaComment")
        title_label.setObjectName("TitleLabel")
        subtitle_label = QLabel("把 TXT 段落一键贴成注释，尽量不打断你在编辑器里的节奏。")
        subtitle_label.setObjectName("SubtitleLabel")
        subtitle_label.setWordWrap(True)
        badge_label = QLabel("Windows 托盘 MVP")
        badge_label.setObjectName("AccentChip")

        header_layout.addWidget(title_label)
        header_layout.addWidget(subtitle_label)
        header_layout.addWidget(badge_label, alignment=Qt.AlignLeft)
        layout.addWidget(header_card)

        file_group = QGroupBox("文件")
        file_group.setObjectName("Card")
        file_layout = QGridLayout(file_group)
        file_layout.setHorizontalSpacing(18)
        file_layout.setVerticalSpacing(12)
        file_layout.setColumnStretch(1, 1)

        file_name_label = QLabel("当前文件")
        file_name_label.setObjectName("MetricLabel")
        encoding_label = QLabel("编码")
        encoding_label.setObjectName("MetricLabel")
        progress_label = QLabel("当前输出")
        progress_label.setObjectName("MetricLabel")
        chapter_label = QLabel("章节跳转")
        chapter_label.setObjectName("MetricLabel")
        recent_files_label = QLabel("阅读列表")
        recent_files_label.setObjectName("MetricLabel")

        self.file_name_value = QLabel("未选择文件")
        self.file_name_value.setObjectName("MetricValue")
        self.file_name_value.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.file_path_hint = QLabel("还没有加载 TXT 文件。")
        self.file_path_hint.setObjectName("PathHint")
        self.file_path_hint.setWordWrap(True)
        self.encoding_value = QLabel("-")
        self.encoding_value.setObjectName("MetricValue")
        self.progress_value = QLabel("0 / 0")
        self.progress_value.setObjectName("MetricValue")
        self.chapter_combo = QComboBox()
        self.chapter_combo.setMinimumHeight(36)
        self.chapter_combo.setEnabled(False)
        self.chapter_combo.currentIndexChanged.connect(self._emit_chapter_selected)
        self.recent_files_list = QListWidget()
        self.recent_files_list.setMinimumHeight(92)
        self.recent_files_list.setMaximumHeight(120)
        self.recent_files_list.setToolTip("双击打开最近阅读过的 TXT 文件。")
        self.recent_files_list.itemDoubleClicked.connect(self._emit_recent_file_selected)

        choose_button = QPushButton("选择 TXT 文件")
        choose_button.setObjectName("PrimaryButton")
        choose_button.setMinimumWidth(190)
        choose_button.setMinimumHeight(42)
        choose_button.clicked.connect(self._open_file_dialog)

        file_layout.addWidget(file_name_label, 0, 0)
        file_layout.addWidget(self.file_name_value, 0, 1)
        file_layout.addWidget(choose_button, 0, 2)
        file_layout.addWidget(self.file_path_hint, 1, 1, 1, 2)
        file_layout.addWidget(encoding_label, 2, 0)
        file_layout.addWidget(self.encoding_value, 2, 1)
        file_layout.addWidget(progress_label, 3, 0)
        file_layout.addWidget(self.progress_value, 3, 1)
        file_layout.addWidget(chapter_label, 4, 0)
        file_layout.addWidget(self.chapter_combo, 4, 1, 1, 2)
        file_layout.addWidget(recent_files_label, 5, 0)
        file_layout.addWidget(self.recent_files_list, 5, 1, 1, 2)
        layout.addWidget(file_group)

        split_group = QGroupBox("输出切分")
        split_group.setObjectName("Card")
        split_layout = QVBoxLayout(split_group)
        split_row = QHBoxLayout()
        split_row.setSpacing(10)

        self.output_mode_group = QButtonGroup(self)
        self.paragraph_mode_radio = QRadioButton("原始段落")
        self.smart_mode_radio = QRadioButton("智能切分")
        self.paragraph_mode_radio.setMinimumHeight(38)
        self.smart_mode_radio.setMinimumHeight(38)
        self.output_mode_group.addButton(self.paragraph_mode_radio)
        self.output_mode_group.addButton(self.smart_mode_radio)
        self.paragraph_mode_radio.toggled.connect(self._emit_output_mode)
        self.smart_mode_radio.toggled.connect(self._emit_output_mode)

        length_label = QLabel("智能切分长度")
        length_label.setObjectName("MetricLabel")
        self.smart_length_spin = QSpinBox()
        self.smart_length_spin.setRange(20, 5000)
        self.smart_length_spin.setSingleStep(10)
        self.smart_length_spin.setSuffix(" 字")
        self.smart_length_spin.setMinimumWidth(140)
        self.smart_length_spin.setMinimumHeight(38)
        self.smart_length_spin.valueChanged.connect(self.smart_chunk_length_changed.emit)

        split_row.addWidget(self.paragraph_mode_radio)
        split_row.addWidget(self.smart_mode_radio)
        split_row.addSpacing(12)
        split_row.addWidget(length_label)
        split_row.addWidget(self.smart_length_spin)
        split_row.addStretch()
        split_layout.addLayout(split_row)

        split_hint = QLabel(
            "智能切分会先按空行拆段，再把超长段落按句子和长度自动切成更适合粘贴的小块。"
        )
        split_hint.setObjectName("HintText")
        split_hint.setWordWrap(True)
        split_layout.addWidget(split_hint)
        layout.addWidget(split_group)

        paste_group = QGroupBox("粘贴行为")
        paste_group.setObjectName("Card")
        paste_layout = QVBoxLayout(paste_group)
        paste_row = QHBoxLayout()
        paste_row.setSpacing(10)

        self.paste_mode_group = QButtonGroup(self)
        self.browse_mode_radio = QRadioButton("浏览模式")
        self.accumulate_mode_radio = QRadioButton("累积模式")
        self.browse_mode_radio.setMinimumHeight(38)
        self.accumulate_mode_radio.setMinimumHeight(38)
        self.paste_mode_group.addButton(self.browse_mode_radio)
        self.paste_mode_group.addButton(self.accumulate_mode_radio)
        self.browse_mode_radio.toggled.connect(self._emit_paste_mode)
        self.accumulate_mode_radio.toggled.connect(self._emit_paste_mode)
        self.restore_clipboard_checkbox = QCheckBox("粘贴后恢复剪贴板")
        self.restore_clipboard_checkbox.setMinimumHeight(38)
        self.restore_clipboard_checkbox.toggled.connect(self.restore_clipboard_changed.emit)

        paste_row.addWidget(self.browse_mode_radio)
        paste_row.addWidget(self.accumulate_mode_radio)
        paste_row.addSpacing(12)
        paste_row.addWidget(self.restore_clipboard_checkbox)
        paste_row.addStretch()
        paste_layout.addLayout(paste_row)

        paste_hint = QLabel(
            "浏览模式会在下一次工具粘贴前先撤销上一段，只保留当前正在看的内容；累积模式会把每一段继续追加到编辑器里。"
        )
        paste_hint.setObjectName("HintText")
        paste_hint.setWordWrap(True)
        paste_layout.addWidget(paste_hint)
        layout.addWidget(paste_group)

        style_group = QGroupBox("注释格式")
        style_group.setObjectName("Card")
        style_layout = QVBoxLayout(style_group)
        style_top_row = QHBoxLayout()
        style_top_row.setSpacing(10)

        self.comment_group = QButtonGroup(self)
        self.slash_radio = QRadioButton("// 行注释")
        self.hash_radio = QRadioButton("# 脚本注释")
        self.slash_radio.setMinimumHeight(38)
        self.hash_radio.setMinimumHeight(38)
        self.comment_group.addButton(self.slash_radio)
        self.comment_group.addButton(self.hash_radio)
        self.slash_radio.setChecked(True)
        self.slash_radio.toggled.connect(self._emit_comment_style)
        self.hash_radio.toggled.connect(self._emit_comment_style)

        style_top_row.addWidget(self.slash_radio)
        style_top_row.addWidget(self.hash_radio)
        style_top_row.addStretch()
        style_layout.addLayout(style_top_row)

        style_hint = QLabel("预览区会显示当前注释格式下实际要粘贴的内容。")
        style_hint.setObjectName("HintText")
        style_hint.setWordWrap(True)
        style_layout.addWidget(style_hint)
        layout.addWidget(style_group)

        preview_group = QGroupBox("当前预览")
        preview_group.setObjectName("Card")
        preview_layout = QVBoxLayout(preview_group)

        preview_note = QLabel("这里显示下一次快捷键触发时会输出的内容，并且已经处理成注释格式。")
        preview_note.setObjectName("HintText")
        preview_note.setWordWrap(True)

        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setMinimumHeight(160)
        self.preview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.preview.setPlaceholderText("选择文件后，这里会显示下一段要输出的注释预览。")

        preview_layout.addWidget(preview_note)
        preview_layout.addWidget(self.preview)
        layout.addWidget(preview_group)

        actions_group = QGroupBox("快捷操作")
        actions_group.setObjectName("Card")
        actions_layout = QVBoxLayout(actions_group)
        actions_row = QHBoxLayout()
        actions_row.setSpacing(10)

        self.previous_button = QPushButton("上一段")
        self.previous_button.setMinimumWidth(110)
        self.previous_button.setMinimumHeight(40)
        self.previous_button.clicked.connect(self.previous_requested.emit)

        self.next_button = QPushButton("下一段并粘贴")
        self.next_button.setObjectName("PrimaryButton")
        self.next_button.setMinimumWidth(150)
        self.next_button.setMinimumHeight(40)
        self.next_button.clicked.connect(self.next_requested.emit)

        self.undo_button = QPushButton("撤销上一次工具粘贴")
        self.undo_button.setObjectName("DangerButton")
        self.undo_button.setMinimumWidth(170)
        self.undo_button.setMinimumHeight(40)
        self.undo_button.clicked.connect(self.undo_requested.emit)

        minimize_button = QPushButton("最小化到托盘")
        minimize_button.setMinimumWidth(140)
        minimize_button.setMinimumHeight(40)
        minimize_button.clicked.connect(self.minimize_requested.emit)

        actions_row.addWidget(self.previous_button)
        actions_row.addWidget(self.next_button)
        actions_row.addWidget(self.undo_button)
        actions_row.addStretch()
        actions_row.addWidget(minimize_button)
        actions_layout.addLayout(actions_row)

        actions_hint = QLabel("平时可以把窗口放到托盘里，直接在编辑器中用快捷键推进。")
        actions_hint.setObjectName("HintText")
        actions_hint.setWordWrap(True)
        actions_layout.addWidget(actions_hint)
        layout.addWidget(actions_group)

        hotkey_group = QGroupBox("全局快捷键")
        hotkey_group.setObjectName("Card")
        hotkey_layout = QGridLayout(hotkey_group)
        hotkey_layout.setHorizontalSpacing(12)
        hotkey_layout.setVerticalSpacing(12)
        hotkey_layout.setColumnStretch(1, 1)

        for row, spec in enumerate(self._hotkey_specs):
            name_label = QLabel(spec.name)
            name_label.setObjectName("HotkeyName")
            name_label.setMinimumWidth(130)

            editor = HotkeyEdit()
            editor.setToolTip("点击输入框后直接按下新的组合键，或者按鼠标侧键。")
            editor.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            editor.capture_started.connect(self.hotkey_capture_started.emit)
            editor.capture_finished.connect(self.hotkey_capture_finished.emit)

            self._hotkey_inputs[spec.action] = editor
            hotkey_layout.addWidget(name_label, row, 0)
            hotkey_layout.addWidget(editor, row, 1)
            hotkey_layout.setRowMinimumHeight(row, 44)

        hotkey_buttons = QHBoxLayout()
        hotkey_buttons.setSpacing(10)

        hotkey_apply_button = QPushButton("应用快捷键")
        hotkey_apply_button.setObjectName("PrimaryButton")
        hotkey_apply_button.setMinimumWidth(140)
        hotkey_apply_button.setMinimumHeight(40)
        hotkey_apply_button.clicked.connect(self._emit_hotkeys_apply)

        hotkey_reset_button = QPushButton("恢复默认")
        hotkey_reset_button.setMinimumWidth(120)
        hotkey_reset_button.setMinimumHeight(40)
        hotkey_reset_button.clicked.connect(self.hotkeys_reset_requested.emit)

        hotkey_buttons.addWidget(hotkey_apply_button)
        hotkey_buttons.addWidget(hotkey_reset_button)
        hotkey_buttons.addStretch()
        hotkey_layout.addLayout(hotkey_buttons, len(self._hotkey_specs), 0, 1, 2)

        hotkey_hint = QLabel(
            "点击输入框后按下新的组合键，或者按鼠标侧键。可以不带 Ctrl/Alt/Shift，但每个动作不能重复。"
        )
        hotkey_hint.setObjectName("HintText")
        hotkey_hint.setWordWrap(True)
        hotkey_layout.addWidget(hotkey_hint, len(self._hotkey_specs) + 1, 0, 1, 2)

        layout.addWidget(hotkey_group)

        self.status_label = QLabel("准备就绪。")
        self.status_label.setObjectName("StatusLabel")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        layout.addStretch()

    def set_session(self, session: SessionState) -> None:
        document = session.document
        if document:
            self._file_path = document.path
            self.file_name_value.setText(document.path.name)
            self.file_name_value.setToolTip(str(document.path))
            self.file_path_hint.setText(str(document.path))
            self.file_path_hint.setToolTip(str(document.path))
            self.encoding_value.setText(document.encoding)
        else:
            self._file_path = None
            self.file_name_value.setText("未选择文件")
            self.file_name_value.setToolTip("")
            self.file_path_hint.setText("还没有加载 TXT 文件。")
            self.file_path_hint.setToolTip("")
            self.encoding_value.setText("-")

        total = session.total_units
        if total == 0:
            self.progress_value.setText("0 / 0")
            self.preview.setPlainText("")
        elif session.next_index >= total:
            self.progress_value.setText(f"{total} / {total} (已到末尾)")
            self.preview.setPlainText("-- 已到最后一段之后，可先按“上一段”回退。")
        else:
            self.progress_value.setText(f"{session.next_index + 1} / {total}")
            self.preview.setPlainText(format_paragraph(session.output_units[session.next_index].text, session.comment_style))

        self._set_chapter_options(session)
        self._apply_comment_style(session.comment_style)
        self.set_output_settings(session.output_mode, session.smart_chunk_length)
        self.set_paste_mode(session.paste_mode)

    def set_recent_files(self, paths: list[Path]) -> None:
        self.recent_files_list.clear()
        for path in paths:
            item = QListWidgetItem(path.name)
            item.setToolTip(str(path))
            item.setData(Qt.UserRole, str(path))
            self.recent_files_list.addItem(item)

    def set_restore_clipboard_after_paste(self, enabled: bool) -> None:
        self.restore_clipboard_checkbox.blockSignals(True)
        self.restore_clipboard_checkbox.setChecked(enabled)
        self.restore_clipboard_checkbox.blockSignals(False)

    def set_output_settings(self, output_mode: OutputMode, smart_chunk_length: int) -> None:
        self.paragraph_mode_radio.blockSignals(True)
        self.smart_mode_radio.blockSignals(True)
        self.smart_length_spin.blockSignals(True)

        self.paragraph_mode_radio.setChecked(output_mode == "paragraph")
        self.smart_mode_radio.setChecked(output_mode == "smart")
        self.smart_length_spin.setValue(smart_chunk_length)
        self.smart_length_spin.setEnabled(output_mode == "smart")

        self.paragraph_mode_radio.blockSignals(False)
        self.smart_mode_radio.blockSignals(False)
        self.smart_length_spin.blockSignals(False)

    def set_paste_mode(self, paste_mode: PasteMode) -> None:
        self.browse_mode_radio.blockSignals(True)
        self.accumulate_mode_radio.blockSignals(True)

        self.browse_mode_radio.setChecked(paste_mode == "browse")
        self.accumulate_mode_radio.setChecked(paste_mode == "accumulate")

        self.browse_mode_radio.blockSignals(False)
        self.accumulate_mode_radio.blockSignals(False)

    def _set_chapter_options(self, session: SessionState) -> None:
        self.chapter_combo.blockSignals(True)
        self.chapter_combo.clear()
        if not session.chapters:
            self.chapter_combo.addItem("未识别到章节", -1)
            self.chapter_combo.setEnabled(False)
            self.chapter_combo.blockSignals(False)
            return

        self.chapter_combo.setEnabled(True)
        current_chapter_index = 0
        for index, chapter in enumerate(session.chapters):
            self.chapter_combo.addItem(chapter.title, chapter.unit_index)
            if chapter.unit_index <= session.next_index:
                current_chapter_index = index
        self.chapter_combo.setCurrentIndex(current_chapter_index)
        self.chapter_combo.blockSignals(False)

    def set_hotkeys(self, hotkey_specs: list[HotkeySpec]) -> None:
        self._hotkey_specs = list(hotkey_specs)
        for spec in hotkey_specs:
            editor = self._hotkey_inputs.get(spec.action)
            if editor:
                editor.set_hotkey(spec.trigger_kind, spec.modifiers, spec.virtual_key, spec.display)

    def current_hotkey_specs(self) -> list[HotkeySpec]:
        specs: list[HotkeySpec] = []
        for spec in self._hotkey_specs:
            editor = self._hotkey_inputs[spec.action]
            trigger_kind, modifiers, virtual_key, display = editor.binding()
            specs.append(
                HotkeySpec(
                    action=spec.action,
                    name=spec.name,
                    hotkey_id=spec.hotkey_id,
                    trigger_kind=trigger_kind,
                    modifiers=modifiers,
                    virtual_key=virtual_key,
                    display=display,
                )
            )
        return specs

    def set_status(self, message: str) -> None:
        self.status_label.setText(message)

    def set_allow_close(self, allow: bool) -> None:
        self._allow_close = allow

    def closeEvent(self, event) -> None:  # type: ignore[override]
        if self._allow_close:
            event.accept()
            return
        event.ignore()
        self.hide()
        self.minimize_requested.emit()

    def _open_file_dialog(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择 TXT 文件",
            str(self._file_path.parent) if self._file_path else "",
            "Text Files (*.txt);;All Files (*)",
        )
        if file_path:
            self.file_selected.emit(file_path)

    def _emit_comment_style(self) -> None:
        if self.slash_radio.isChecked():
            self.comment_style_changed.emit("//")
        elif self.hash_radio.isChecked():
            self.comment_style_changed.emit("#")

    def _emit_output_mode(self) -> None:
        if self.paragraph_mode_radio.isChecked():
            self.output_mode_changed.emit("paragraph")
            self.smart_length_spin.setEnabled(False)
        elif self.smart_mode_radio.isChecked():
            self.output_mode_changed.emit("smart")
            self.smart_length_spin.setEnabled(True)

    def _emit_paste_mode(self) -> None:
        if self.browse_mode_radio.isChecked():
            self.paste_mode_changed.emit("browse")
        elif self.accumulate_mode_radio.isChecked():
            self.paste_mode_changed.emit("accumulate")

    def _emit_recent_file_selected(self, item: QListWidgetItem) -> None:
        path = item.data(Qt.UserRole)
        if path:
            self.recent_file_selected.emit(str(path))

    def _emit_chapter_selected(self) -> None:
        unit_index = self.chapter_combo.currentData()
        if isinstance(unit_index, int) and unit_index >= 0:
            self.chapter_selected.emit(unit_index)

    def _emit_hotkeys_apply(self) -> None:
        self.hotkeys_apply_requested.emit(self.current_hotkey_specs())

    def _apply_comment_style(self, style: str) -> None:
        self.slash_radio.blockSignals(True)
        self.hash_radio.blockSignals(True)
        self.slash_radio.setChecked(style == "//")
        self.hash_radio.setChecked(style == "#")
        self.slash_radio.blockSignals(False)
        self.hash_radio.blockSignals(False)
