"""Helpers for building, validating, and serializing global hotkeys."""

from __future__ import annotations

from typing import Any, Mapping

from app.config import DEFAULT_HOTKEYS, HOTKEY_IDS, MOD_ALT, MOD_CONTROL, MOD_SHIFT
from app.models import HotkeySpec, HotkeyTriggerKind

ACTION_ORDER: tuple[str, ...] = tuple(DEFAULT_HOTKEYS.keys())

TRIGGER_KIND_KEYBOARD: HotkeyTriggerKind = "keyboard"
TRIGGER_KIND_MOUSE: HotkeyTriggerKind = "mouse"

MOUSE_BUTTON_BACK = 1
MOUSE_BUTTON_FORWARD = 2

NUMPAD_KEY_LABELS = {
    0x60: "Num 0",
    0x61: "Num 1",
    0x62: "Num 2",
    0x63: "Num 3",
    0x64: "Num 4",
    0x65: "Num 5",
    0x66: "Num 6",
    0x67: "Num 7",
    0x68: "Num 8",
    0x69: "Num 9",
}

MOUSE_BUTTON_LABELS = {
    MOUSE_BUTTON_BACK: "鼠标后退键",
    MOUSE_BUTTON_FORWARD: "鼠标前进键",
}


def default_hotkey_specs() -> list[HotkeySpec]:
    """Return the default hotkey set."""
    return build_hotkey_specs()


def build_hotkey_specs(
    saved_hotkeys: Mapping[str, Mapping[str, Any]] | None = None,
) -> list[HotkeySpec]:
    """Build runtime hotkey specs from saved state or defaults."""
    specs: list[HotkeySpec] = []
    hotkeys_map = saved_hotkeys if isinstance(saved_hotkeys, Mapping) else {}

    for action in ACTION_ORDER:
        default = DEFAULT_HOTKEYS[action]
        saved = hotkeys_map.get(action, {})

        modifiers = _coerce_int(saved.get("modifiers"), default["modifiers"])
        virtual_key = _coerce_int(saved.get("virtual_key"), default["virtual_key"])
        trigger_kind = normalize_trigger_kind(saved.get("trigger_kind"))
        display = saved.get("display")
        if not isinstance(display, str) or not display.strip():
            if trigger_kind == TRIGGER_KIND_MOUSE:
                display = format_mouse_display(modifiers, virtual_key)
            else:
                display = default["display"]

        if trigger_kind == TRIGGER_KIND_KEYBOARD:
            display = format_keyboard_display(modifiers, virtual_key, str(display))

        specs.append(
            HotkeySpec(
                action=action,
                name=str(default["name"]),
                hotkey_id=HOTKEY_IDS[action],
                trigger_kind=trigger_kind,
                modifiers=modifiers,
                virtual_key=virtual_key,
                display=display,
            )
        )

    return specs


def serialize_hotkey_specs(specs: list[HotkeySpec]) -> dict[str, dict[str, int | str]]:
    """Convert hotkey specs into JSON-friendly state."""
    return {
        spec.action: {
            "trigger_kind": spec.trigger_kind,
            "modifiers": spec.modifiers,
            "virtual_key": spec.virtual_key,
            "display": spec.display,
        }
        for spec in specs
    }


def find_duplicate_hotkeys(specs: list[HotkeySpec]) -> list[str]:
    """Return user-facing duplicate descriptions."""
    duplicates: list[str] = []
    seen: dict[tuple[str, int, int], str] = {}

    for spec in specs:
        combo = (spec.trigger_kind, spec.modifiers, spec.virtual_key)
        previous = seen.get(combo)
        if previous:
            duplicates.append(f"{previous} / {spec.name} ({spec.display})")
        else:
            seen[combo] = spec.name

    return duplicates


def find_hotkey_warnings(specs: list[HotkeySpec]) -> list[str]:
    """Return non-blocking warnings for risky global hotkey choices."""
    warnings: list[str] = []
    common_shortcuts = {
        (MOD_CONTROL, 0x41): "Ctrl+A",
        (MOD_CONTROL, 0x43): "Ctrl+C",
        (MOD_CONTROL, 0x46): "Ctrl+F",
        (MOD_CONTROL, 0x53): "Ctrl+S",
        (MOD_CONTROL, 0x56): "Ctrl+V",
        (MOD_CONTROL, 0x58): "Ctrl+X",
        (MOD_CONTROL, 0x5A): "Ctrl+Z",
        (MOD_CONTROL | MOD_SHIFT, 0x5A): "Ctrl+Shift+Z",
        (MOD_ALT, 0x09): "Alt+Tab",
        (MOD_ALT, 0x73): "Alt+F4",
    }

    for spec in specs:
        if spec.trigger_kind != TRIGGER_KIND_KEYBOARD:
            continue

        shortcut = common_shortcuts.get((spec.modifiers, spec.virtual_key))
        if shortcut:
            warnings.append(f"{spec.name} 使用了常见快捷键 {shortcut}，可能会抢占编辑器或系统功能。")
            continue

        if spec.modifiers == 0:
            warnings.append(f"{spec.name} 使用了单键 {spec.display}，可能会影响正常输入或光标移动。")

    return warnings


def normalize_trigger_kind(value: object) -> HotkeyTriggerKind:
    if value == TRIGGER_KIND_MOUSE:
        return TRIGGER_KIND_MOUSE
    return TRIGGER_KIND_KEYBOARD


def mouse_button_label(button_code: int) -> str:
    return MOUSE_BUTTON_LABELS.get(button_code, f"鼠标按键 {button_code}")


def format_modifier_prefix(modifiers: int) -> str:
    parts: list[str] = []
    if modifiers & MOD_CONTROL:
        parts.append("Ctrl")
    if modifiers & MOD_ALT:
        parts.append("Alt")
    if modifiers & MOD_SHIFT:
        parts.append("Shift")
    return "+".join(parts)


def format_mouse_display(modifiers: int, button_code: int) -> str:
    prefix = format_modifier_prefix(modifiers)
    label = mouse_button_label(button_code)
    return f"{prefix}+{label}" if prefix else label


def format_keyboard_display(modifiers: int, virtual_key: int, fallback: str = "") -> str:
    """Return a clearer display label for keyboard hotkeys when possible."""
    label = NUMPAD_KEY_LABELS.get(virtual_key)
    if not label:
        return fallback

    prefix = format_modifier_prefix(modifiers)
    return f"{prefix}+{label}" if prefix else label


def _coerce_int(value: object, fallback: int) -> int:
    if isinstance(value, int):
        return value
    return fallback
