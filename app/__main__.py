"""Allow ParaComment to run with ``python -m app``."""

from __future__ import annotations

from app.main import main

if __name__ == "__main__":
    raise SystemExit(main())
