from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.services.text_loader import (
    build_output_units,
    detect_chapters,
    format_paragraph,
    load_text_file,
    smart_split_paragraph,
    split_paragraphs,
)


class TextLoaderTests(unittest.TestCase):
    def test_split_paragraphs_filters_blank_blocks(self) -> None:
        text = "alpha\n\n\nbeta\nline\n\n   \ngamma"
        self.assertEqual(split_paragraphs(text), ["alpha", "beta\nline", "gamma"])

    def test_load_utf8_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "utf8.txt"
            file_path.write_text("one\n\ntwo", encoding="utf-8")
            loaded = load_text_file(file_path)
            self.assertEqual(loaded.encoding, "utf-8")
            self.assertEqual(loaded.paragraphs, ["one", "two"])

    def test_load_gbk_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "gbk.txt"
            file_path.write_bytes("\u4e2d\u6587\u6bb5\u843d\n\n\u7b2c\u4e8c\u6bb5".encode("gbk"))
            loaded = load_text_file(file_path)
            self.assertIn(loaded.encoding, {"gb18030", "gbk", "gb2312", "cp936"})
            self.assertEqual(loaded.paragraphs, ["中文段落", "第二段"])

    def test_format_paragraph_prefixes_each_line(self) -> None:
        paragraph = "line1\nline2"
        formatted = format_paragraph(paragraph, "//")
        self.assertEqual(formatted, "// line1\r\n// line2")

    def test_smart_split_paragraph_breaks_long_content(self) -> None:
        paragraph = "第一句很短。第二句也不长。第三句稍微长一点，但是仍然是自然的一句。第四句收尾。"
        chunks = smart_split_paragraph(paragraph, 20)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(chunk[0]) <= 20 for chunk in chunks))

    def test_build_output_units_supports_paragraph_and_smart_mode(self) -> None:
        paragraphs = [
            "第一句很短。第二句稍微长一点。第三句再补一点。",
        ]
        paragraph_units = build_output_units(paragraphs, "paragraph", 120)
        smart_units = build_output_units(paragraphs, "smart", 12)
        self.assertEqual(len(paragraph_units), 1)
        self.assertGreater(len(smart_units), 1)

    def test_detect_chapters_maps_titles_to_output_units(self) -> None:
        paragraphs = [
            "第1章 开始",
            "第一段正文。",
            "Chapter 2 Return",
            "第二段正文。",
        ]
        units = build_output_units(paragraphs, "paragraph", 120)
        chapters = detect_chapters(paragraphs, units)

        self.assertEqual([chapter.title for chapter in chapters], ["第1章 开始", "Chapter 2 Return"])
        self.assertEqual([chapter.unit_index for chapter in chapters], [0, 2])


if __name__ == "__main__":
    unittest.main()
