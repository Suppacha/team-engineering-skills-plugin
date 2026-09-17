#!/usr/bin/env python3
"""Build the deliberately small, trusted updater runtime archive."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import tempfile
import zipfile

from release_files import release_files
from team_updater.cli import runtime_files


ROOT = Path(__file__).resolve().parents[1]
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


def build(output: Path) -> None:
    output = output.expanduser().absolute()
    output.parent.mkdir(parents=True, exist_ok=True)
    released = dict(release_files(ROOT))
    selected = []
    for name in sorted(runtime_files()):
        source = released.get(name)
        if source is None or source.is_symlink() or not source.is_file():
            raise RuntimeError(f"trusted-runtime-unavailable: {name}")
        selected.append((name, source))

    descriptor, temporary_name = tempfile.mkstemp(prefix=".updater-", suffix=".zip",
                                                   dir=output.parent)
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED,
                             compresslevel=9) as archive:
            for name, source in selected:
                info = zipfile.ZipInfo(name, ZIP_TIMESTAMP)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                archive.writestr(info, source.read_bytes(), compress_type=zipfile.ZIP_DEFLATED,
                                 compresslevel=9)
        os.replace(temporary, output)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    build(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
