#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MARKETPLACE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PLUGIN_ROOT="${MARKETPLACE_ROOT}/plugins/team-engineering-skills"
TEST_PYTHON="${PYTHON_BIN:-python3}"

resolve_codex_validator() {
    local installed_validator path_validator
    if [[ -n "${CODEX_PLUGIN_VALIDATOR:-}" ]]; then
        if [[ -f "${CODEX_PLUGIN_VALIDATOR}" ]]; then
            printf '%s\n' "${CODEX_PLUGIN_VALIDATOR}"
            return 0
        fi
        printf 'CODEX_PLUGIN_VALIDATOR does not point to a file: %s\n' "${CODEX_PLUGIN_VALIDATOR}" >&2
        return 1
    fi
    if [[ -n "${CODEX_HOME:-}" ]]; then
        installed_validator="${CODEX_HOME}/skills/.system/plugin-creator/scripts/validate_plugin.py"
        if [[ -f "${installed_validator}" ]]; then
            printf '%s\n' "${installed_validator}"
            return 0
        fi
    fi
    if [[ -n "${HOME:-}" ]]; then
        installed_validator="${HOME}/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py"
        if [[ -f "${installed_validator}" ]]; then
            printf '%s\n' "${installed_validator}"
            return 0
        fi
    fi
    path_validator="$(command -v validate_plugin.py 2>/dev/null || true)"
    if [[ -n "${path_validator}" && -f "${path_validator}" ]]; then
        printf '%s\n' "${path_validator}"
        return 0
    fi
    return 1
}

find_yaml_python() {
    local candidate
    for candidate in "${CODEX_VALIDATOR_PYTHON:-}" python python3; do
        if [[ -n "${candidate}" ]] && command -v "${candidate}" >/dev/null 2>&1 \
            && "${candidate}" -c 'import yaml' >/dev/null 2>&1; then
            printf '%s\n' "${candidate}"
            return 0
        fi
    done
    return 1
}

cd "${MARKETPLACE_ROOT}"
if [[ "${SKIP_PORTABLE_TESTS:-0}" != "1" ]]; then
    printf 'Python package tests...\n'
    "${TEST_PYTHON}" scripts/verify-portable.py
fi

printf 'Framework metadata gate...\n'
"${TEST_PYTHON}" - "${PLUGIN_ROOT}" <<'PY'
import sys
from pathlib import Path
sys.dont_write_bytecode = True
plugin = Path(sys.argv[1])
sys.path.insert(0, str(plugin / "scripts"))
from framework import validate_release
registry = validate_release(plugin)
print(f"Framework {registry['version']}: {len(registry['skills'])} skill payloads and all standards verified")
PY

printf 'JSON manifest parsing...\n'
"${TEST_PYTHON}" - "${MARKETPLACE_ROOT}" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
for relative_path in (
    ".agents/plugins/marketplace.json",
    ".claude-plugin/marketplace.json",
    "plugins/team-engineering-skills/.claude-plugin/plugin.json",
    "plugins/team-engineering-skills/.codex-plugin/plugin.json",
):
    json.loads((root / relative_path).read_text(encoding="utf-8"))
print("JSON parsing passed")
PY

if ! VALIDATOR_PATH="$(resolve_codex_validator)"; then
    printf 'Codex plugin validator SKIPPED: unavailable; install plugin-creator or set CODEX_PLUGIN_VALIDATOR. Portable checks passed.\n'
elif ! VALIDATOR_PYTHON="$(find_yaml_python)"; then
    printf 'Codex plugin validator SKIPPED: PyYAML unavailable; set CODEX_VALIDATOR_PYTHON. Portable checks passed.\n'
else
    printf 'Codex plugin validator...\n'
    "${VALIDATOR_PYTHON}" "${VALIDATOR_PATH}" "${PLUGIN_ROOT}"
fi

if command -v claude >/dev/null 2>&1; then
    printf 'Claude plugin validator...\n'
    claude plugin validate "${PLUGIN_ROOT}"
else
    printf 'Claude plugin validator SKIPPED: claude CLI is not installed.\n'
fi

printf 'Package verification PASS\n'
