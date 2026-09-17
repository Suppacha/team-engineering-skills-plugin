#!/usr/bin/env python3
"""Frozen updater entry point."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from team_updater.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
