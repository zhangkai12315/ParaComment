"""Global hotkey registration on Windows for keyboard and mouse side buttons."""

from __future__ import annotations

import ctypes
from ctypes import wintypes

from PySide6.QtCore import QAbstractNativeEventFilter, QCoreApplication, QObject, Qt, QTimer, Signal

from app.config import MOD_ALT, MOD_CONTROL, MOD_SHIFT
from app.hotkeys import TRIGGER_KIND_KEYBOARD, TRIGGER_KIND_MOUSE, default_hotkey_specs
from app.models import HotkeySpec
from app.services.debug_logger import DebugLogger

WM_HOTKEY = 0x0312
PM_REMOVE = 0x0001
WH_KEYBOARD_LL = 13
WH_MOUSE_LL = 14
HC_ACTION = 0
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
WM_XBUTTONDOWN = 0x020B
WM_XBUTTONUP = 0x020C
XBUTTON1 = 0x0001
XBUTTON2 = 0x0002
LLKHF_INJECTED = 0x0010
VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
LRESULT = ctypes.c_ssize_t
HHOOK = wintypes.HANDLE


class MSG(ctypes.Structure):
    _fields_ = (
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt", wintypes.POINT),
    )


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = (
        ("pt", wintypes.POINT),
        ("mouseData", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    )


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = (
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    )


LowLevelKeyboardProc = ctypes.WINFUNCTYPE(
    LRESULT,
    ctypes.c_int,
    wintypes.WPARAM,
    wintypes.LPARAM,
)


LowLevelMouseProc = ctypes.WINFUNCTYPE(
    LRESULT,
    ctypes.c_int,
    wintypes.WPARAM,
    wintypes.LPARAM,
)

user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
user32.RegisterHotKey.restype = wintypes.BOOL
user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
user32.UnregisterHotKey.restype = wintypes.BOOL
user32.PeekMessageW.argtypes = [ctypes.POINTER(MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT, wintypes.UINT]
user32.PeekMessageW.restype = wintypes.BOOL
user32.SetWindowsHookExW.argtypes = [ctypes.c_int, ctypes.c_void_p, wintypes.HINSTANCE, wintypes.DWORD]
user32.SetWindowsHookExW.restype = HHOOK
user32.UnhookWindowsHookEx.argtypes = [HHOOK]
user32.UnhookWindowsHookEx.restype = wintypes.BOOL
user32.CallNextHookEx.argtypes = [HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
user32.CallNextHookEx.restype = LRESULT
user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
user32.GetAsyncKeyState.restype = ctypes.c_short


class HotkeyService(QObject):
    """Register hotkeys and emit signals when they are pressed."""

    hotkey_pressed = Signal(str)
    _queued_hotkey = Signal(str)
    _queued_keyboard_hotkey = Signal(str)

    def __init__(self, specs: list[HotkeySpec] | None = None, logger: DebugLogger | None = None) -> None:
        super().__init__()
        self._specs = list(specs) if specs else default_hotkey_specs()
        self._logger = logger
        self._timer = QTimer(self)
        self._timer.setInterval(50)
        self._timer.timeout.connect(self._pump_messages)
        self._queued_hotkey.connect(self._dispatch_queued_hotkey, Qt.QueuedConnection)
        self._queued_keyboard_hotkey.connect(self._dispatch_queued_keyboard_hotkey, Qt.QueuedConnection)
        self._registered_ids: set[int] = set()
        self._native_event_filter = _HotkeyNativeEventFilter(self)
        self._native_filter_seen = False
        self._keyboard_specs: list[HotkeySpec] = []
        self._keyboard_hook_handle = None
        self._keyboard_hook_proc = None
        self._keyboard_hook_error = 0
        self._pending_keyboard_actions: dict[int, str] = {}
        self._mouse_specs: list[HotkeySpec] = []
        self._mouse_hook_handle = None
        self._mouse_hook_proc = None
        self._mouse_hook_error = 0
        self._pending_mouse_button: int | None = None
        self._pending_mouse_action: str | None = None

    def start(self) -> list[str]:
        """Register all configured hotkeys and return any failures."""
        self._log("hotkey.start", specs=[self._spec_to_record(spec) for spec in self._specs])
        errors: list[str] = []
        self._keyboard_specs = [spec for spec in self._specs if spec.trigger_kind == TRIGGER_KIND_KEYBOARD]
        self._mouse_specs = [spec for spec in self._specs if spec.trigger_kind == TRIGGER_KIND_MOUSE]
        self._keyboard_hook_error = 0
        self._mouse_hook_error = 0

        if self._keyboard_specs and not self._install_keyboard_hook():
            self._log(
                "hotkey.register.keyboard",
                success=False,
                error_code=self._keyboard_hook_error,
                specs=[self._spec_to_record(spec) for spec in self._keyboard_specs],
            )
            errors.extend(f"{spec.name} ({spec.display})" for spec in self._keyboard_specs)

        if self._mouse_specs and not self._install_mouse_hook():
            self._log(
                "hotkey.register.mouse",
                success=False,
                error_code=self._mouse_hook_error,
                specs=[self._spec_to_record(spec) for spec in self._mouse_specs],
            )
            errors.extend(f"{spec.name} ({spec.display})" for spec in self._mouse_specs)

        self._log(
            "hotkey.start.completed",
            registered_ids=sorted(self._registered_ids),
            keyboard_hook_installed=bool(self._keyboard_hook_handle),
            mouse_hook_installed=bool(self._mouse_hook_handle),
            failures=errors,
        )
        return errors

    def stop(self) -> None:
        self._log(
            "hotkey.stop",
            registered_ids=sorted(self._registered_ids),
            keyboard_hook_installed=bool(self._keyboard_hook_handle),
            mouse_hook_installed=bool(self._mouse_hook_handle),
        )
        self._timer.stop()
        self._update_native_event_filter(enable=False)
        for hotkey_id in list(self._registered_ids):
            user32.UnregisterHotKey(None, hotkey_id)
        self._registered_ids.clear()
        self._remove_keyboard_hook()
        self._remove_mouse_hook()

    def specs(self) -> list[HotkeySpec]:
        return list(self._specs)

    def replace_specs(self, specs: list[HotkeySpec]) -> list[str]:
        """Replace registered hotkeys and roll back if the new set fails."""
        previous_specs = list(self._specs)
        self._log(
            "hotkey.replace.requested",
            specs=[self._spec_to_record(spec) for spec in specs],
        )
        self.stop()
        self._specs = list(specs)
        errors = self.start()
        if errors:
            self._log("hotkey.replace.rollback", failures=errors)
            self.stop()
            self._specs = previous_specs
            self.start()
        else:
            self._log("hotkey.replace.completed", specs=[self._spec_to_record(spec) for spec in specs])
        return errors

    def _pump_messages(self) -> None:
        handled = 0
        msg = MSG()
        while user32.PeekMessageW(ctypes.byref(msg), None, WM_HOTKEY, WM_HOTKEY, PM_REMOVE):
            handled += 1
            self._log("hotkey.keyboard.message", hotkey_id=int(msg.wParam))
            self._handle_hotkey_message(int(msg.wParam))
            msg = MSG()

        if handled:
            self._log("hotkey.keyboard_pump.handled", count=handled)

    def _action_for_id(self, hotkey_id: int) -> str | None:
        for spec in self._specs:
            if spec.hotkey_id == hotkey_id:
                return spec.action
        return None

    def _install_keyboard_hook(self) -> bool:
        self._keyboard_hook_proc = LowLevelKeyboardProc(self._keyboard_proc)
        ctypes.set_last_error(0)
        self._keyboard_hook_handle = user32.SetWindowsHookExW(
            WH_KEYBOARD_LL,
            ctypes.cast(self._keyboard_hook_proc, ctypes.c_void_p),
            None,
            0,
        )
        self._keyboard_hook_error = ctypes.get_last_error()
        self._log(
            "hotkey.keyboard_hook.install",
            success=bool(self._keyboard_hook_handle),
            error_code=self._keyboard_hook_error,
            specs=[self._spec_to_record(spec) for spec in self._keyboard_specs],
        )
        return bool(self._keyboard_hook_handle)

    def _remove_keyboard_hook(self) -> None:
        if self._keyboard_hook_handle:
            self._log("hotkey.keyboard_hook.remove", handle=self._hook_handle_value(self._keyboard_hook_handle))
            user32.UnhookWindowsHookEx(self._keyboard_hook_handle)
        self._keyboard_hook_handle = None
        self._keyboard_hook_proc = None
        self._keyboard_specs = []
        self._pending_keyboard_actions.clear()

    def _keyboard_proc(self, n_code: int, w_param: int, l_param: int):
        if n_code == HC_ACTION and w_param in {WM_KEYDOWN, WM_SYSKEYDOWN, WM_KEYUP, WM_SYSKEYUP}:
            hook_struct = ctypes.cast(l_param, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
            if hook_struct.flags & LLKHF_INJECTED:
                return user32.CallNextHookEx(self._keyboard_hook_handle, n_code, w_param, l_param)

            vk_code = int(hook_struct.vkCode)
            if w_param in {WM_KEYDOWN, WM_SYSKEYDOWN}:
                if vk_code in self._pending_keyboard_actions:
                    self._log(
                        "hotkey.keyboard.repeat_ignored",
                        virtual_key=vk_code,
                        action=self._pending_keyboard_actions.get(vk_code),
                    )
                    return 1

                modifiers = self._current_modifiers()
                action = self._matching_keyboard_action(vk_code, modifiers)
                if action:
                    self._pending_keyboard_actions[vk_code] = action
                    self._log("hotkey.keyboard.trigger", virtual_key=vk_code, modifiers=modifiers, action=action)
                    self._queued_keyboard_hotkey.emit(action)
                    QTimer.singleShot(250, lambda vk_code=vk_code: self._clear_stale_keyboard_action(vk_code))
                    return 1
            else:
                action = self._pending_keyboard_actions.pop(vk_code, None)
                if action:
                    self._log("hotkey.keyboard.release", virtual_key=vk_code, action=action)
                    return 1

        return user32.CallNextHookEx(self._keyboard_hook_handle, n_code, w_param, l_param)

    def _install_mouse_hook(self) -> bool:
        self._mouse_hook_proc = LowLevelMouseProc(self._mouse_proc)
        ctypes.set_last_error(0)
        self._mouse_hook_handle = user32.SetWindowsHookExW(
            WH_MOUSE_LL,
            ctypes.cast(self._mouse_hook_proc, ctypes.c_void_p),
            None,
            0,
        )
        self._mouse_hook_error = ctypes.get_last_error()
        self._log(
            "hotkey.mouse_hook.install",
            success=bool(self._mouse_hook_handle),
            error_code=self._mouse_hook_error,
        )
        return bool(self._mouse_hook_handle)

    def _remove_mouse_hook(self) -> None:
        if self._mouse_hook_handle:
            self._log("hotkey.mouse_hook.remove", handle=self._hook_handle_value(self._mouse_hook_handle))
            user32.UnhookWindowsHookEx(self._mouse_hook_handle)
        self._mouse_hook_handle = None
        self._mouse_hook_proc = None
        self._mouse_specs = []
        self._pending_mouse_button = None
        self._pending_mouse_action = None

    def _mouse_proc(self, n_code: int, w_param: int, l_param: int):
        if n_code == HC_ACTION and w_param in {WM_XBUTTONDOWN, WM_XBUTTONUP}:
            hook_struct = ctypes.cast(l_param, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
            button_code = (hook_struct.mouseData >> 16) & 0xFFFF

            if w_param == WM_XBUTTONDOWN:
                modifiers = self._current_modifiers()
                self._log(
                    "hotkey.mouse.down",
                    button_code=button_code,
                    modifiers=modifiers,
                    action=self._matching_mouse_action(button_code, modifiers),
                )
                if self._begin_mouse_action(button_code, modifiers):
                    self._queued_hotkey.emit(self._pending_mouse_action or "")
                    return 1
            else:
                action = self._finish_mouse_action(button_code)
                self._log("hotkey.mouse.up", button_code=button_code, action=action)
                if action:
                    return 1

        return user32.CallNextHookEx(self._mouse_hook_handle, n_code, w_param, l_param)

    def _begin_mouse_action(self, button_code: int, modifiers: int) -> bool:
        action = self._matching_mouse_action(button_code, modifiers)
        if not action:
            return False
        self._pending_mouse_button = button_code
        self._pending_mouse_action = action
        self._log("hotkey.mouse.begin", button_code=button_code, modifiers=modifiers, action=action)
        return True

    def _finish_mouse_action(self, button_code: int) -> str | None:
        if self._pending_mouse_button != button_code:
            self._log(
                "hotkey.mouse.finish_mismatch",
                expected_button=self._pending_mouse_button,
                actual_button=button_code,
            )
            return None
        action = self._pending_mouse_action
        self._pending_mouse_button = None
        self._pending_mouse_action = None
        self._log("hotkey.mouse.finish", button_code=button_code, action=action)
        return action

    def _matching_mouse_action(self, button_code: int, modifiers: int) -> str | None:
        for spec in self._mouse_specs:
            if spec.virtual_key == button_code and spec.modifiers == modifiers:
                return spec.action
        return None

    def _matching_keyboard_action(self, virtual_key: int, modifiers: int) -> str | None:
        for spec in self._keyboard_specs:
            if spec.virtual_key == virtual_key and spec.modifiers == modifiers:
                return spec.action
        return None

    def _clear_stale_keyboard_action(self, virtual_key: int) -> None:
        action = self._pending_keyboard_actions.pop(virtual_key, None)
        if action:
            self._log("hotkey.keyboard.auto_release", virtual_key=virtual_key, action=action)

    def _dispatch_queued_hotkey(self, action: str) -> None:
        if not action:
            return
        self._log("hotkey.dispatch.queued", action=action, delay_ms=0)
        QTimer.singleShot(0, lambda action=action: self._emit_hotkey(action))

    def _dispatch_queued_keyboard_hotkey(self, action: str) -> None:
        if not action:
            return
        self._log("hotkey.dispatch.keyboard_queued", action=action, delay_ms=0)
        QTimer.singleShot(0, lambda action=action: self._emit_hotkey(action))

    def _log(self, event: str, **fields: object) -> None:
        if self._logger:
            self._logger.log(event, **fields)

    def _emit_hotkey(self, action: str) -> None:
        self._log("hotkey.dispatch.emit", action=action)
        self.hotkey_pressed.emit(action)

    @staticmethod
    def _spec_to_record(spec: HotkeySpec) -> dict[str, int | str]:
        return {
            "action": spec.action,
            "name": spec.name,
            "trigger_kind": spec.trigger_kind,
            "modifiers": spec.modifiers,
            "virtual_key": spec.virtual_key,
            "display": spec.display,
        }

    @staticmethod
    def _hook_handle_value(handle) -> int:
        return int(getattr(handle, "value", handle) or 0)

    @staticmethod
    def _current_modifiers() -> int:
        modifiers = 0
        if user32.GetAsyncKeyState(VK_CONTROL) & 0x8000:
            modifiers |= MOD_CONTROL
        if user32.GetAsyncKeyState(VK_MENU) & 0x8000:
            modifiers |= MOD_ALT
        if user32.GetAsyncKeyState(VK_SHIFT) & 0x8000:
            modifiers |= MOD_SHIFT
        return modifiers

    @staticmethod
    def _ensure_message_queue() -> None:
        msg = MSG()
        user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0)

    def _handle_hotkey_message(self, hotkey_id: int) -> None:
        action = self._action_for_id(hotkey_id)
        if not action:
            return
        self._log("hotkey.keyboard.fired", hotkey_id=hotkey_id, action=action)
        self.hotkey_pressed.emit(action)

    def _update_native_event_filter(self, enable: bool | None = None) -> None:
        app = QCoreApplication.instance()
        if app is None:
            return

        should_enable = bool(self._registered_ids) if enable is None else enable
        if should_enable:
            self._ensure_message_queue()
            app.installNativeEventFilter(self._native_event_filter)
            self._timer.stop()
        else:
            app.removeNativeEventFilter(self._native_event_filter)
            self._timer.stop()


class _HotkeyNativeEventFilter(QAbstractNativeEventFilter):
    """Listen for WM_HOTKEY messages from the Qt Windows event loop."""

    def __init__(self, service: HotkeyService) -> None:
        super().__init__()
        self._service = service

    def nativeEventFilter(self, event_type, message):  # type: ignore[override]
        event_name = event_type.decode("ascii", errors="ignore") if isinstance(event_type, (bytes, bytearray)) else str(event_type)
        if event_name not in {"windows_generic_MSG", "windows_dispatcher_MSG"}:
            return False, 0

        if not self._service._native_filter_seen:
            self._service._native_filter_seen = True
            self._service._log("hotkey.native.filter_seen", event_name=event_name)

        msg = ctypes.cast(message, ctypes.POINTER(MSG)).contents
        if msg.message != WM_HOTKEY:
            return False, 0

        self._service._log("hotkey.native.wm_hotkey", hotkey_id=int(msg.wParam), event_name=event_name)
        self._service._handle_hotkey_message(int(msg.wParam))
        return False, 0
