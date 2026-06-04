from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.services.debug_logger import DebugLogger


class DebugLoggerTests(unittest.TestCase):
    def test_log_writes_json_line(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "debug.log"
            logger = DebugLogger(log_path)

            logger.log("paste.start", action="next", count=1)

            self.assertTrue(log_path.exists())
            records = log_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(records), 1)

            payload = json.loads(records[0])
            self.assertEqual(payload["event"], "paste.start")
            self.assertEqual(payload["fields"]["action"], "next")
            self.assertEqual(payload["fields"]["count"], 1)


if __name__ == "__main__":
    unittest.main()
