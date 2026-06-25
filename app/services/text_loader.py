"""Text loading, encoding detection, paragraph parsing, and smart splitting."""

from __future__ import annotations

import re
from pathlib import Path

from charset_normalizer import from_bytes

from app.models import ChapterInfo, LoadedText, OutputMode, OutputUnit

UTF8_BOM = b"\xef\xbb\xbf"
UTF16_LE_BOM = b"\xff\xfe"
UTF16_BE_BOM = b"\xfe\xff"
UTF32_LE_BOM = b"\xff\xfe\x00\x00"
UTF32_BE_BOM = b"\x00\x00\xfe\xff"

GB_ENCODINGS = {
    "gb18030",
    "gb2312",
    "gbk",
    "cp936",
}

CHAPTER_TITLE_PATTERN = re.compile(
    r"^\s*(?:"
    r"第[0-9零〇一二三四五六七八九十百千万两]+[章节回卷集部篇].{0,50}"
    r"|Chapter\s+\d+.{0,50}"
    r"|CHAPTER\s+\d+.{0,50}"
    r"|[0-9]{1,4}\s*[、.．]\s*.{1,50}"
    r")\s*$",
    re.IGNORECASE,
)

PRIMARY_BREAK_CHARS = {"。", "！", "？", "!", "?", "\n"}
SECONDARY_BREAK_CHARS = {"；", "，", ";", ",", "、", "\n"}


def detect_encoding(raw: bytes) -> str:
    """Detect a practical text encoding for Chinese TXT input."""
    if raw.startswith(UTF32_LE_BOM):
        return "utf-32-le"
    if raw.startswith(UTF32_BE_BOM):
        return "utf-32-be"
    if raw.startswith(UTF8_BOM):
        return "utf-8-sig"
    if raw.startswith(UTF16_LE_BOM):
        return "utf-16-le"
    if raw.startswith(UTF16_BE_BOM):
        return "utf-16-be"

    try:
        raw.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        pass

    best_guess = from_bytes(raw).best()
    if best_guess and best_guess.encoding:
        guess = best_guess.encoding.lower().replace("_", "-")
        if guess in GB_ENCODINGS:
            return "gb18030"
        if guess in {"ascii", "utf-8", "utf-8-sig"}:
            return "utf-8"
        if guess.startswith("utf-16"):
            return "utf-16"
        if guess.startswith("utf-32"):
            return "utf-32"

    return "gb18030"


def split_paragraphs(text: str) -> list[str]:
    """Split text into non-empty paragraphs separated by blank lines."""
    normalized = normalize_text(text)
    parts = re.split(r"\n\s*\n+", normalized)
    return [part.strip() for part in parts if part.strip()]


def load_text_file(path: str | Path) -> LoadedText:
    """Load and parse a text file."""
    file_path = Path(path)
    raw = file_path.read_bytes()
    encoding = detect_encoding(raw)

    try:
        text = raw.decode(encoding)
    except UnicodeDecodeError:
        if encoding != "gb18030":
            text = raw.decode("gb18030")
            encoding = "gb18030"
        else:
            text = raw.decode("utf-8", errors="replace")
            encoding = "utf-8 (replace)"

    return LoadedText(
        path=file_path,
        encoding=encoding,
        paragraphs=split_paragraphs(text),
    )


def build_output_units(
    paragraphs: list[str],
    output_mode: OutputMode,
    smart_chunk_length: int,
) -> list[OutputUnit]:
    """Build final output units based on the selected splitting strategy."""
    units: list[OutputUnit] = []
    chunk_length = validate_smart_chunk_length(smart_chunk_length)

    for paragraph_index, paragraph in enumerate(paragraphs):
        normalized = normalize_text(paragraph).strip()
        if not normalized:
            continue

        if output_mode == "paragraph":
            chunks = [(normalized, 0, len(normalized))]
        else:
            chunks = smart_split_paragraph(normalized, chunk_length)

        for chunk_index, (text, char_start, char_end) in enumerate(chunks):
            if text.strip():
                units.append(
                    OutputUnit(
                        text=text,
                        paragraph_index=paragraph_index,
                        chunk_index=chunk_index,
                        char_start=char_start,
                        char_end=char_end,
                    )
                )

    return units


def detect_chapters(paragraphs: list[str], output_units: list[OutputUnit]) -> list[ChapterInfo]:
    """Detect chapter-like headings and map them to output unit indexes."""
    first_unit_by_paragraph: dict[int, int] = {}
    for index, unit in enumerate(output_units):
        first_unit_by_paragraph.setdefault(unit.paragraph_index, index)

    chapters: list[ChapterInfo] = []
    for paragraph_index, paragraph in enumerate(paragraphs):
        title = _chapter_title_from_paragraph(paragraph)
        if not title:
            continue

        unit_index = first_unit_by_paragraph.get(paragraph_index)
        if unit_index is None:
            unit_index = _next_unit_after_paragraph(output_units, paragraph_index)
        if unit_index is None:
            continue

        chapters.append(
            ChapterInfo(
                title=title,
                paragraph_index=paragraph_index,
                unit_index=unit_index,
            )
        )

    return chapters


def smart_split_paragraph(paragraph: str, max_length: int) -> list[tuple[str, int, int]]:
    """Split a paragraph into smaller natural chunks."""
    normalized = normalize_text(paragraph).strip()
    if not normalized:
        return []

    max_length = validate_smart_chunk_length(max_length)
    if len(normalized) <= max_length:
        return [(normalized, 0, len(normalized))]

    fragments = _split_fragments(normalized, 0, len(normalized), PRIMARY_BREAK_CHARS)
    if len(fragments) <= 1:
        return _split_oversized_fragment(normalized, 0, len(normalized), max_length)

    return _pack_fragments(normalized, fragments, max_length)


def validate_smart_chunk_length(value: int) -> int:
    """Clamp the smart split length to a practical range."""
    if value < 20:
        return 20
    if value > 5000:
        return 5000
    return int(value)


def format_paragraph(paragraph: str, comment_style: str) -> str:
    """Prefix every line in a paragraph with the configured comment style."""
    prefix = f"{comment_style} "
    lines = normalize_text(paragraph).split("\n")
    commented = [prefix + line.rstrip() for line in lines]
    return "\r\n".join(commented)


def normalize_text(text: str) -> str:
    """Normalize line endings to Unix style for internal processing."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _chapter_title_from_paragraph(paragraph: str) -> str | None:
    lines = [line.strip() for line in normalize_text(paragraph).split("\n") if line.strip()]
    if not lines:
        return None

    first_line = lines[0]
    if len(first_line) > 80:
        return None
    if CHAPTER_TITLE_PATTERN.match(first_line):
        return first_line
    return None


def _next_unit_after_paragraph(output_units: list[OutputUnit], paragraph_index: int) -> int | None:
    for index, unit in enumerate(output_units):
        if unit.paragraph_index >= paragraph_index:
            return index
    return None


def _pack_fragments(
    original: str,
    fragments: list[tuple[str, int, int]],
    max_length: int,
) -> list[tuple[str, int, int]]:
    chunks: list[tuple[str, int, int]] = []
    current_start: int | None = None
    current_end = 0
    current_length = 0

    for fragment_text, fragment_start, fragment_end in fragments:
        fragment_length = len(fragment_text)
        if fragment_length > max_length:
            if current_start is not None:
                chunks.append(_trimmed_slice(original, current_start, current_end))
                current_start = None
                current_length = 0
            chunks.extend(_split_oversized_fragment(original, fragment_start, fragment_end, max_length))
            continue

        if current_start is None:
            current_start = fragment_start
            current_end = fragment_end
            current_length = fragment_length
            continue

        if current_length + fragment_length > max_length:
            chunks.append(_trimmed_slice(original, current_start, current_end))
            current_start = fragment_start
            current_end = fragment_end
            current_length = fragment_length
        else:
            current_end = fragment_end
            current_length += fragment_length

    if current_start is not None:
        chunks.append(_trimmed_slice(original, current_start, current_end))

    return [chunk for chunk in chunks if chunk[0].strip()]


def _split_oversized_fragment(
    original: str,
    start: int,
    end: int,
    max_length: int,
) -> list[tuple[str, int, int]]:
    fragments = _split_fragments(original, start, end, SECONDARY_BREAK_CHARS)
    if len(fragments) > 1:
        return _pack_fragments(original, fragments, max_length)
    return _fixed_length_chunks(original, start, end, max_length)


def _split_fragments(
    original: str,
    start: int,
    end: int,
    separators: set[str],
) -> list[tuple[str, int, int]]:
    fragments: list[tuple[str, int, int]] = []
    cursor = start

    for index in range(start, end):
        if original[index] in separators:
            fragment = _trimmed_slice(original, cursor, index + 1)
            if fragment[0]:
                fragments.append(fragment)
            cursor = index + 1

    if cursor < end:
        fragment = _trimmed_slice(original, cursor, end)
        if fragment[0]:
            fragments.append(fragment)

    return fragments


def _fixed_length_chunks(original: str, start: int, end: int, max_length: int) -> list[tuple[str, int, int]]:
    chunks: list[tuple[str, int, int]] = []
    cursor = start

    while cursor < end:
        cursor = _skip_leading_whitespace(original, cursor, end)
        if cursor >= end:
            break

        tentative_end = min(end, cursor + max_length)
        if tentative_end < end:
            preferred_end = _find_preferred_cut(original, cursor, tentative_end)
            if preferred_end > cursor:
                tentative_end = preferred_end

        chunk = _trimmed_slice(original, cursor, tentative_end)
        if chunk[0]:
            chunks.append(chunk)
        cursor = tentative_end

    return chunks


def _find_preferred_cut(original: str, start: int, tentative_end: int) -> int:
    minimum_cut = start + max(1, (tentative_end - start) // 2)
    preferred_chars = PRIMARY_BREAK_CHARS | SECONDARY_BREAK_CHARS | {" ", "\t"}

    for index in range(tentative_end - 1, minimum_cut - 1, -1):
        if original[index] in preferred_chars:
            return index + 1

    return tentative_end


def _trimmed_slice(original: str, start: int, end: int) -> tuple[str, int, int]:
    while start < end and original[start].isspace():
        start += 1
    while end > start and original[end - 1].isspace():
        end -= 1
    return original[start:end], start, end


def _skip_leading_whitespace(original: str, start: int, end: int) -> int:
    while start < end and original[start].isspace():
        start += 1
    return start
