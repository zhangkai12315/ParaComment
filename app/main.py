"""ParaComment application entry point."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from app import __version__
from app.hotkeys import build_hotkey_specs, default_hotkey_specs, find_duplicate_hotkeys, find_hotkey_warnings
from app.models import HotkeySpec, OutputUnit, PasteMode, SessionState
from app.services.debug_logger import DebugLogger
from app.services.hotkey_service import HotkeyService
from app.services.paste_service import PasteService
from app.services.state_store import StateStore
from app.services.text_loader import build_output_units, detect_chapters, format_paragraph, load_text_file
from app.services.tray_service import TrayService
from app.ui.main_window import MainWindow
from app.ui.theme import apply_app_theme


class ParaCommentController:
    """Coordinate UI, state, and editor output behavior."""

    def __init__(self, app: QApplication) -> None:
        self.app = app
        self.app.setQuitOnLastWindowClosed(False)
        self.debug_logger = DebugLogger()
        self.state_store = StateStore()
        self.paste_service = PasteService(self.debug_logger)
        initial_hotkeys = build_hotkey_specs(self.state_store.load_hotkeys())
        self.hotkey_service = HotkeyService(initial_hotkeys, self.debug_logger)
        defaults = self.state_store.load_settings()
        self.restore_clipboard_after_paste = bool(defaults["restore_clipboard_after_paste"])
        self.paste_service.set_restore_clipboard_after_paste(self.restore_clipboard_after_paste)
        self.session = SessionState(
            output_mode=str(defaults["default_output_mode"]),
            smart_chunk_length=int(defaults["default_smart_chunk_length"]),
            paste_mode=str(defaults["default_paste_mode"]),
        )
        self.window = MainWindow(self.hotkey_service.specs())
        self.window.set_output_settings(self.session.output_mode, self.session.smart_chunk_length)
        self.window.set_paste_mode(self.session.paste_mode)
        self.window.set_restore_clipboard_after_paste(self.restore_clipboard_after_paste)
        self.tray = TrayService(self.window)
        self._hotkeys_paused_for_capture = False
        self._connect_signals()
        self.debug_logger.log(
            "controller.initialized",
            debug_log_path=self.debug_logger.path,
            default_output_mode=self.session.output_mode,
            default_smart_chunk_length=self.session.smart_chunk_length,
            default_paste_mode=self.session.paste_mode,
            restore_clipboard_after_paste=self.restore_clipboard_after_paste,
        )

    def start(self) -> None:
        self.debug_logger.log("controller.start")
        failures = self.hotkey_service.start()
        if failures:
            self.debug_logger.log("controller.start.hotkey_failures", failures=failures)
            self.window.set_status("以下快捷键注册失败，可能已被其他程序占用：" + "，".join(failures))
            self.tray.show_message("ParaComment", "部分快捷键注册失败，请打开主窗口查看详情。")

        self.window.set_hotkeys(self.hotkey_service.specs())
        self.window.set_output_settings(self.session.output_mode, self.session.smart_chunk_length)
        self.window.set_paste_mode(self.session.paste_mode)
        self.window.set_restore_clipboard_after_paste(self.restore_clipboard_after_paste)
        self.window.set_recent_files(self.state_store.get_recent_files())

        recent_file = self.state_store.get_recent_file()
        if recent_file and recent_file.exists():
            self.debug_logger.log("controller.start.restore_recent_file", path=recent_file)
            self.open_file(recent_file)
        else:
            self.window.set_session(self.session)
            self.window.set_status("请选择一个 TXT 小说文件开始。")

        self.tray.show()
        self.show_window()
        self.debug_logger.log("controller.ready")

    def shutdown(self) -> None:
        self.debug_logger.log("controller.shutdown")
        self.window.set_allow_close(True)
        self.hotkey_service.stop()
        self.tray.tray_icon.hide()
        self.window.close()
        self.app.quit()

    def open_file(self, file_path: str | Path) -> None:
        self.debug_logger.log("controller.open_file.requested", file_path=file_path)
        try:
            document = load_text_file(file_path)
        except FileNotFoundError:
            self.debug_logger.log("controller.open_file.not_found", file_path=file_path)
            self.window.set_status("文件不存在，请重新选择。")
            self.tray.show_message("ParaComment", "文件不存在，请重新选择。")
            return
        except OSError as exc:
            self.debug_logger.log("controller.open_file.error", file_path=file_path, error=str(exc))
            self.window.set_status(f"读取文件失败：{exc}")
            self.tray.show_message("ParaComment", "读取文件失败，请检查文件是否被占用。")
            return

        progress = self.state_store.load_progress(document.path)
        self.session = SessionState(
            document=document,
            next_index=progress.next_index,
            comment_style=progress.comment_style,
            output_mode=progress.output_mode,
            smart_chunk_length=progress.smart_chunk_length,
            paste_mode=progress.paste_mode,
        )
        self._rebuild_output_units(preserve_position=False)
        self.state_store.set_recent_file(document.path)
        self._persist_session()
        self.window.set_recent_files(self.state_store.get_recent_files())
        self.window.set_session(self.session)
        self.debug_logger.log(
            "controller.open_file.completed",
            path=document.path,
            encoding=document.encoding,
            paragraph_count=len(document.paragraphs),
            output_units=self.session.total_units,
            chapter_count=len(self.session.chapters),
            next_index=self.session.next_index,
            paste_mode=self.session.paste_mode,
        )
        self.window.set_status(
            f"已加载 {document.path.name}，识别编码 {document.encoding}，共 {self.session.total_units} 个输出片段，识别到 {len(self.session.chapters)} 个章节。"
        )

    def paste_next(self) -> None:
        self.debug_logger.log(
            "controller.paste_next.requested",
            has_document=bool(self.session.document),
            next_index=self.session.next_index,
            total_units=self.session.total_units,
            paste_mode=self.session.paste_mode,
        )
        if not self.session.document:
            self.window.set_status("请先选择 TXT 文件。")
            self.show_window()
            return

        if self.session.next_index >= self.session.total_units:
            self.window.set_status("已经到最后一段，没有更多内容可粘贴。")
            self.tray.show_message("ParaComment", "已经到最后一段。")
            self.window.set_session(self.session)
            return

        replaced_current = False
        if self.session.paste_mode == "browse" and self.session.paste_history:
            current_index = self.session.next_index
            self._replace_paste_index(current_index)
            replaced_current = True
        else:
            current_index = self.session.next_index
            self._paste_index(current_index)
        self._persist_session()
        self.window.set_session(self.session)
        self.debug_logger.log(
            "controller.paste_next.completed",
            pasted_index=current_index,
            next_index=self.session.next_index,
            replaced_current=replaced_current,
        )
        if self.session.paste_mode == "browse":
            self.window.set_status(f"已切换到第 {current_index + 1} 个片段。")
        else:
            self.window.set_status(f"已输出第 {current_index + 1} 个片段。")

    def move_previous(self) -> None:
        self.debug_logger.log(
            "controller.move_previous.requested",
            has_document=bool(self.session.document),
            next_index=self.session.next_index,
            paste_mode=self.session.paste_mode,
        )
        if not self.session.document:
            self.window.set_status("请先选择 TXT 文件。")
            return

        if self.session.paste_mode == "browse" and self.session.paste_history:
            current_index = self.session.paste_history[-1]
            if current_index <= 0:
                self.window.set_status("已经在第一段，无法继续回退。")
                return

            target_index = current_index - 1
            self._replace_paste_index(target_index)
            self._persist_session()
            self.window.set_session(self.session)
            self.debug_logger.log(
                "controller.move_previous.completed",
                next_index=self.session.next_index,
                pasted_index=target_index,
                replaced_current=True,
            )
            self.window.set_status(f"已切换到第 {target_index + 1} 个片段。")
            return

        if self.session.next_index <= 0:
            self.window.set_status("已经在第一段之前，无法继续回退。")
            return

        target_index = self.session.next_index - 1
        if self.session.paste_mode == "browse":
            self._paste_index(target_index)
            self._persist_session()
            self.window.set_session(self.session)
            self.debug_logger.log(
                "controller.move_previous.completed",
                next_index=self.session.next_index,
                pasted_index=target_index,
                replaced_current=False,
            )
            self.window.set_status(f"已切换到第 {target_index + 1} 个片段。")
            return

        self.session.next_index = target_index
        self._persist_session()
        self.window.set_session(self.session)
        self.debug_logger.log("controller.move_previous.completed", next_index=self.session.next_index)
        self.window.set_status(f"已回退到第 {self.session.next_index + 1} 个片段。")

    def undo_last_paste(self) -> None:
        self.debug_logger.log(
            "controller.undo.requested",
            history_size=len(self.session.paste_history),
            paste_mode=self.session.paste_mode,
        )
        if not self.session.paste_history:
            self.window.set_status("当前会话里没有可撤销的工具粘贴记录。")
            return

        last_index = self._undo_tracked_paste(reset_next_index=True)
        if last_index is None:
            self.window.set_status("当前会话里没有可撤销的工具粘贴记录。")
            return

        self._persist_session()
        self.window.set_session(self.session)
        self.debug_logger.log("controller.undo.completed", restored_index=last_index)
        self.window.set_status(f"已尝试撤销第 {last_index + 1} 个片段的工具粘贴。")

    def set_comment_style(self, style: str) -> None:
        if style not in {"//", "#"}:
            return
        self.session.comment_style = style
        self._persist_session()
        self.window.set_session(self.session)
        self.window.set_status(f"注释格式已切换为 {style}。")

    def set_output_mode(self, mode: str) -> None:
        if mode not in {"paragraph", "smart"}:
            return
        if self.session.output_mode == mode:
            return

        self.session.output_mode = mode  # type: ignore[assignment]
        self.state_store.save_settings(
            self.session.output_mode,
            self.session.smart_chunk_length,
            self.session.paste_mode,
            self.restore_clipboard_after_paste,
        )

        if self.session.document:
            self._rebuild_output_units(preserve_position=True)
            self._persist_session()
            self.window.set_session(self.session)
        else:
            self.window.set_output_settings(self.session.output_mode, self.session.smart_chunk_length)

        status_text = "已切换为智能切分。" if mode == "smart" else "已切换为原始段落输出。"
        self.window.set_status(status_text)

    def set_smart_chunk_length(self, value: int) -> None:
        if self.session.smart_chunk_length == value:
            return

        self.session.smart_chunk_length = int(value)
        self.state_store.save_settings(
            self.session.output_mode,
            self.session.smart_chunk_length,
            self.session.paste_mode,
            self.restore_clipboard_after_paste,
        )

        if self.session.document:
            self._rebuild_output_units(preserve_position=True)
            self._persist_session()
            self.window.set_session(self.session)
        else:
            self.window.set_output_settings(self.session.output_mode, self.session.smart_chunk_length)

        self.window.set_status(f"智能切分长度已更新为 {self.session.smart_chunk_length} 字。")

    def set_paste_mode(self, mode: str) -> None:
        if mode not in {"browse", "accumulate"}:
            return
        if self.session.paste_mode == mode:
            return

        self.session.paste_mode = mode  # type: ignore[assignment]
        self.state_store.save_settings(
            self.session.output_mode,
            self.session.smart_chunk_length,
            self.session.paste_mode,
            self.restore_clipboard_after_paste,
        )

        if self.session.paste_mode == "browse" and len(self.session.paste_history) > 1:
            self.session.paste_history.clear()
            status_text = "已切换为浏览模式。为避免误撤销，已重置当前工具粘贴跟踪。"
        else:
            status_text = "已切换为浏览模式。" if mode == "browse" else "已切换为累积模式。"

        self._persist_session()
        self.window.set_session(self.session)
        self.window.set_paste_mode(self.session.paste_mode)
        self.window.set_status(status_text)

    def set_restore_clipboard_after_paste(self, enabled: bool) -> None:
        self.restore_clipboard_after_paste = bool(enabled)
        self.paste_service.set_restore_clipboard_after_paste(self.restore_clipboard_after_paste)
        self.state_store.save_settings(
            self.session.output_mode,
            self.session.smart_chunk_length,
            self.session.paste_mode,
            self.restore_clipboard_after_paste,
        )
        self.window.set_restore_clipboard_after_paste(self.restore_clipboard_after_paste)
        status_text = "已开启粘贴后恢复剪贴板。" if self.restore_clipboard_after_paste else "已关闭粘贴后恢复剪贴板。"
        self.debug_logger.log(
            "controller.clipboard_restore.changed",
            enabled=self.restore_clipboard_after_paste,
        )
        self.window.set_status(status_text)

    def jump_to_chapter(self, unit_index: int) -> None:
        if not self.session.document or not self.session.output_units:
            return

        target_index = max(0, min(int(unit_index), self.session.total_units - 1))
        self.session.next_index = target_index
        self._persist_session()
        self.window.set_session(self.session)
        self.debug_logger.log(
            "controller.chapter.jump",
            target_index=target_index,
            total_units=self.session.total_units,
        )
        self.window.set_status(f"已跳转到第 {target_index + 1} 个片段，下一次快捷键会从这里输出。")

    def apply_hotkeys(self, specs: object) -> None:
        self.debug_logger.log("controller.hotkeys.apply_requested", specs=specs)
        self._hotkeys_paused_for_capture = False
        if not isinstance(specs, list):
            self.window.set_status("快捷键配置格式无效，请重新输入。")
            return

        validation_error = self._validate_hotkey_specs(specs)
        if validation_error:
            self.window.set_status(validation_error)
            return

        errors = self.hotkey_service.replace_specs(specs)
        if errors:
            self.debug_logger.log("controller.hotkeys.apply_failed", failures=errors)
            self.window.set_hotkeys(self.hotkey_service.specs())
            self.window.set_status("以下快捷键注册失败，可能已被其他程序占用：" + "，".join(errors))
            self.tray.show_message("ParaComment", "快捷键更新失败，已自动恢复到之前可用的配置。")
            return

        self.state_store.save_hotkeys(specs)
        self.window.set_hotkeys(self.hotkey_service.specs())
        warnings = find_hotkey_warnings(specs)
        self.debug_logger.log("controller.hotkeys.apply_completed", warnings=warnings)
        if warnings:
            self.window.set_status("全局快捷键已更新，但建议留意：" + "；".join(warnings[:2]))
        else:
            self.window.set_status("全局快捷键已更新并立即生效。")

    def reset_hotkeys_to_default(self) -> None:
        self.apply_hotkeys(default_hotkey_specs())

    def show_window(self) -> None:
        self.window.showNormal()
        self.window.raise_()
        self.window.activateWindow()
        self.tray.update_window_action(True)

    def hide_window(self) -> None:
        self.window.hide()
        self.tray.update_window_action(False)

    def minimize_to_tray(self) -> None:
        self.hide_window()
        self.tray.show_message("ParaComment", "ParaComment 已最小化到系统托盘。")

    def _persist_session(self) -> None:
        if self.session.document:
            self.debug_logger.log(
                "controller.session.persist",
                path=self.session.document.path,
                next_index=self.session.next_index,
                comment_style=self.session.comment_style,
                output_mode=self.session.output_mode,
                smart_chunk_length=self.session.smart_chunk_length,
                paste_mode=self.session.paste_mode,
            )
            self.state_store.save_progress(
                self.session.document.path,
                self.session.next_index,
                self.session.comment_style,
                self.session.output_mode,
                self.session.smart_chunk_length,
                self.session.paste_mode,
            )
        self.window.set_session(self.session)

    def _rebuild_output_units(self, preserve_position: bool) -> None:
        if not self.session.document:
            self.session.output_units = []
            self.session.chapters = []
            self.session.next_index = 0
            return

        old_units = list(self.session.output_units)
        old_next_index = self.session.next_index
        anchor: OutputUnit | None = None
        at_end = False

        if preserve_position and old_units:
            if old_next_index >= len(old_units):
                anchor = old_units[-1]
                at_end = True
            else:
                anchor = old_units[old_next_index]

        self.session.output_units = build_output_units(
            self.session.document.paragraphs,
            self.session.output_mode,
            self.session.smart_chunk_length,
        )
        self.session.chapters = detect_chapters(self.session.document.paragraphs, self.session.output_units)

        if not self.session.output_units:
            self.session.next_index = 0
            self.session.chapters = []
            self.session.paste_history.clear()
            return

        if anchor is None:
            self.session.next_index = min(self.session.next_index, len(self.session.output_units))
        elif at_end:
            self.session.next_index = len(self.session.output_units)
        else:
            self.session.next_index = self._find_unit_index(anchor)

        self.session.paste_history = [
            index for index in self.session.paste_history if 0 <= index < len(self.session.output_units)
        ]
        if self.session.paste_mode == "browse" and len(self.session.paste_history) > 1:
            self.session.paste_history = self.session.paste_history[-1:]

    def _find_unit_index(self, anchor: OutputUnit) -> int:
        same_paragraph = [
            (index, unit)
            for index, unit in enumerate(self.session.output_units)
            if unit.paragraph_index == anchor.paragraph_index
        ]
        for index, unit in same_paragraph:
            if unit.char_start >= anchor.char_start:
                return index
        if same_paragraph:
            return same_paragraph[-1][0]

        for index, unit in enumerate(self.session.output_units):
            if unit.paragraph_index > anchor.paragraph_index:
                return index
        return len(self.session.output_units)

    def _connect_signals(self) -> None:
        self.window.file_selected.connect(self.open_file)
        self.window.recent_file_selected.connect(self.open_file)
        self.window.chapter_selected.connect(self.jump_to_chapter)
        self.window.comment_style_changed.connect(self.set_comment_style)
        self.window.output_mode_changed.connect(self.set_output_mode)
        self.window.paste_mode_changed.connect(self.set_paste_mode)
        self.window.restore_clipboard_changed.connect(self.set_restore_clipboard_after_paste)
        self.window.smart_chunk_length_changed.connect(self.set_smart_chunk_length)
        self.window.hotkeys_apply_requested.connect(self.apply_hotkeys)
        self.window.hotkeys_reset_requested.connect(self.reset_hotkeys_to_default)
        self.window.hotkey_capture_started.connect(self._pause_hotkeys_for_capture)
        self.window.hotkey_capture_finished.connect(self._resume_hotkeys_after_capture)
        self.window.next_requested.connect(self.paste_next)
        self.window.previous_requested.connect(self.move_previous)
        self.window.undo_requested.connect(self.undo_last_paste)
        self.window.minimize_requested.connect(self.minimize_to_tray)

        self.tray.show_requested.connect(self.show_window)
        self.tray.hide_requested.connect(self.hide_window)
        self.tray.next_requested.connect(self.paste_next)
        self.tray.previous_requested.connect(self.move_previous)
        self.tray.undo_requested.connect(self.undo_last_paste)
        self.tray.quit_requested.connect(self.shutdown)

        self.hotkey_service.hotkey_pressed.connect(self._handle_hotkey)

    def _handle_hotkey(self, action: str) -> None:
        self.debug_logger.log("controller.hotkey.received", action=action)
        if action == "next":
            self.paste_next()
        elif action == "previous":
            self.move_previous()
        elif action == "undo":
            self.undo_last_paste()

    @staticmethod
    def _validate_hotkey_specs(specs: list[HotkeySpec]) -> str | None:
        duplicates = find_duplicate_hotkeys(specs)
        if duplicates:
            return "快捷键不能重复：" + "；".join(duplicates)

        for spec in specs:
            if spec.virtual_key == 0 or not spec.display.strip():
                return f"{spec.name} 的快捷键无效，请重新录入。"

        return None

    def _paste_index(self, index: int) -> None:
        unit = self.session.output_units[index]
        formatted = format_paragraph(unit.text, self.session.comment_style)
        self.debug_logger.log(
            "controller.paste_next.executing",
            current_index=index,
            comment_style=self.session.comment_style,
            text_length=len(formatted),
            preview=formatted[:120],
            paste_mode=self.session.paste_mode,
        )
        self.paste_service.paste_text(formatted)
        if self.session.paste_mode == "browse":
            self.session.paste_history = [index]
        else:
            self.session.paste_history.append(index)
        self.session.next_index = index + 1

    def _replace_paste_index(self, index: int) -> None:
        unit = self.session.output_units[index]
        formatted = format_paragraph(unit.text, self.session.comment_style)
        previous_index = self.session.paste_history.pop() if self.session.paste_history else None
        self.debug_logger.log(
            "controller.paste_replace.executing",
            previous_index=previous_index,
            current_index=index,
            comment_style=self.session.comment_style,
            text_length=len(formatted),
            preview=formatted[:120],
            paste_mode=self.session.paste_mode,
        )
        self.paste_service.replace_text(formatted)
        self.session.paste_history = [index]
        self.session.next_index = index + 1

    def _undo_tracked_paste(self, reset_next_index: bool) -> int | None:
        if not self.session.paste_history:
            return None

        last_index = self.session.paste_history.pop()
        self.debug_logger.log(
            "controller.undo.executing",
            last_index=last_index,
            reset_next_index=reset_next_index,
            paste_mode=self.session.paste_mode,
        )
        self.paste_service.undo_last_paste()
        if reset_next_index:
            self.session.next_index = last_index
        return last_index

    def _pause_hotkeys_for_capture(self) -> None:
        if self._hotkeys_paused_for_capture:
            return
        self.debug_logger.log("controller.hotkeys.capture.pause")
        self.hotkey_service.stop()
        self._hotkeys_paused_for_capture = True

    def _resume_hotkeys_after_capture(self) -> None:
        if not self._hotkeys_paused_for_capture:
            return
        self.debug_logger.log("controller.hotkeys.capture.resume")
        failures = self.hotkey_service.start()
        self._hotkeys_paused_for_capture = False
        if failures:
            self.debug_logger.log("controller.hotkeys.capture.resume_failures", failures=failures)
            self.window.set_status("以下快捷键恢复失败，可能已被其他程序占用：" + "，".join(failures))


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("ParaComment")
    app.setApplicationDisplayName("ParaComment")
    app.setApplicationVersion(__version__)
    apply_app_theme(app)
    controller = ParaCommentController(app)
    controller.window.setWindowIcon(controller.tray.tray_icon.icon())
    controller.start()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
