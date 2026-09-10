#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MARKETPLACE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PLUGIN_ROOT="${MARKETPLACE_ROOT}/plugins/team-engineering-skills"
VERSION="$(tr -d '\r\n' < "${PLUGIN_ROOT}/VERSION")"
OUTPUT_PATH="${MARKETPLACE_ROOT}/dist/team-engineering-skills-marketplace-${VERSION}.zip"
BUILD_PYTHON="${PYTHON_BIN:-python3}"

"${SCRIPT_DIR}/verify-package.sh"
mkdir -p "${MARKETPLACE_ROOT}/dist"

"${BUILD_PYTHON}" - "${MARKETPLACE_ROOT}" "${OUTPUT_PATH}" <<'PY'
"""Create a byte-reproducible marketplace archive using only Python's stdlib."""
from __future__ import annotations

import stat
import sys
import zipfile
from pathlib import Path, PurePosixPath

root = Path(sys.argv[1]).resolve()
output = Path(sys.argv[2]).resolve()
sys.dont_write_bytecode = True
sys.path.insert(0, str(root / "scripts"))
from release_files import release_files
timestamp = (1980, 1, 1, 0, 0, 0)
files = release_files(root)

with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
    for archive_name, path in sorted(files):
        info = zipfile.ZipInfo(PurePosixPath(archive_name).as_posix(), date_time=timestamp)
        info.create_system = 3
        info.compress_type = zipfile.ZIP_DEFLATED
        source_mode = stat.S_IMODE(path.stat().st_mode)
        normalized_mode = 0o755 if source_mode & 0o111 else 0o644
        info.external_attr = (stat.S_IFREG | normalized_mode) << 16
        archive.writestr(info, path.read_bytes())

print(f"Created deterministic archive: {output}")
PY

printf 'Release build PASS: %s\n' "${OUTPUT_PATH}"
