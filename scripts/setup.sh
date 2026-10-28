#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
CALLER_DIR="$PWD"
PROJECT_NAME="my-hack"
WORKSPACE="$ROOT_DIR"

usage() {
    cat <<'EOF'
Usage: scripts/setup.sh [--name NAME] [--workspace PATH]

Prepare the Python environment and initialize/validate a SQLite project.
No ROM is downloaded, copied, opened, or required.

Options:
  --name NAME         Project name (default: my-hack)
  --workspace PATH    Workspace root (default: repository root)
  -h, --help          Show this help

Use scripts/setup.ps1 with the equivalent -Name and -Workspace parameters
from PowerShell on Windows.
EOF
}

fail() {
    printf 'setup: %s\n' "$*" >&2
    exit 2
}

while (($#)); do
    case "$1" in
        --name)
            (($# >= 2)) || fail "--name requires a value"
            PROJECT_NAME="$2"
            shift 2
            ;;
        --workspace)
            (($# >= 2)) || fail "--workspace requires a path"
            WORKSPACE="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            fail "unknown argument: $1 (use --help)"
            ;;
    esac
done

[[ "$PROJECT_NAME" =~ ^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$ ]] ||
    fail "project name must be 1-64 characters and use letters, digits, '-' or '_'"

if [[ "$WORKSPACE" != /* ]]; then
    WORKSPACE="$CALLER_DIR/$WORKSPACE"
fi
mkdir -p -- "$WORKSPACE"
WORKSPACE="$(cd -- "$WORKSPACE" && pwd)"
PROJECT_DIR="$WORKSPACE/project"
DATABASE="$PROJECT_DIR/$PROJECT_NAME.db"
JSON_EXPORT="$PROJECT_DIR/$PROJECT_NAME.json"

if [[ -e "$DATABASE" || -e "$JSON_EXPORT" ]]; then
    fail "refusing to overwrite an existing project: $DATABASE or $JSON_EXPORT"
fi

if command -v uv >/dev/null 2>&1; then
    (cd "$ROOT_DIR" && uv sync --extra dev)
    CLI=(uv run zelda-suite)
else
    if command -v python3 >/dev/null 2>&1; then
        PYTHON_BIN="$(command -v python3)"
    elif command -v python >/dev/null 2>&1; then
        PYTHON_BIN="$(command -v python)"
    else
        fail "uv or Python 3.12+ is required to prepare the environment"
    fi

    VENV="$ROOT_DIR/.venv"
    VENV_PYTHON="$VENV/bin/python"
    if [[ ! -x "$VENV_PYTHON" ]]; then
        "$PYTHON_BIN" -m venv "$VENV"
    fi
    "$VENV_PYTHON" -m pip install --upgrade pip
    (cd "$ROOT_DIR" && "$VENV_PYTHON" -m pip install -e ".[dev]")
    CLI=("$VENV/bin/zelda-suite")
    [[ -x "${CLI[0]}" ]] || fail "installation did not create ${CLI[0]}"
fi

cd "$ROOT_DIR"
"${CLI[@]}" --help >/dev/null
"${CLI[@]}" init "$PROJECT_NAME" --workspace "$WORKSPACE"
"${CLI[@]}" validate "$DATABASE"

printf '\nSetup complete. Project: %s\n' "$DATABASE"
printf 'No ROM was fetched or modified. ROM-dependent checks are optional; see docs/doctor.md.\n'
