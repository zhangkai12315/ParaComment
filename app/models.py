"""Shared application data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

CommentStyle = Literal["//", "#"]
HotkeyTriggerKind = Literal["keyboard", "mouse"]
OutputMode = Literal["paragraph", "smart"]
PasteMode = Literal["browse", "accumulate"]


@dataclass(slots=True)
class LoadedText:
    """A parsed text file ready for paragraph-by-paragraph output."""

    path: Path
    encoding: str
    paragraphs: list[str]


@dataclass(slots=True)
class OutputUnit:
    """A final output chunk ready to paste into the editor."""

    text: str
    paragraph_index: int
    chunk_index: int
    char_start: int
    char_end: int


@dataclass(frozen=True, slots=True)
class ChapterInfo:
    """A detected chapter and the first output unit it maps to."""

    title: str
    paragraph_index: int
    unit_index: int


@dataclass(slots=True)
class FileProgress:
    """Persisted position and per-file display settings."""

    next_index: int = 0
    comment_style: CommentStyle = "//"
    output_mode: OutputMode = "smart"
    smart_chunk_length: int = 120
    paste_mode: PasteMode = "browse"


@dataclass(frozen=True, slots=True)
class HotkeySpec:
    """A global hotkey registration."""

    action: str
    name: str
    hotkey_id: int
    trigger_kind: HotkeyTriggerKind
    modifiers: int
    virtual_key: int
    display: str


@dataclass(frozen=True, slots=True)
class PasteOutcome:
    """Result of inserting text, optionally after removing previous text."""

    inserted: bool
    previous_removed: bool | None = None

    @property
    def fully_succeeded(self) -> bool:
        return self.inserted and self.previous_removed is not False


@dataclass(slots=True)
class SessionState:
    """In-memory runtime session."""

    document: LoadedText | None = None
    output_units: list[OutputUnit] = field(default_factory=list)
    chapters: list[ChapterInfo] = field(default_factory=list)
    next_index: int = 0
    comment_style: CommentStyle = "//"
    output_mode: OutputMode = "smart"
    smart_chunk_length: int = 120
    paste_mode: PasteMode = "browse"
    paste_history: list[int] = field(default_factory=list)

    @property
    def total_units(self) -> int:
        return len(self.output_units)

    @property
    def current_unit(self) -> OutputUnit | None:
        if 0 <= self.next_index < len(self.output_units):
            return self.output_units[self.next_index]
        return None
