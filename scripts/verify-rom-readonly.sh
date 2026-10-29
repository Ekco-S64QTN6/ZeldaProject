#!/usr/bin/env bash
# Run the repository's read-only ROM checks and preserve every JSON report.
set -Eeuo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
CALLER_DIR="$PWD"
EXPECTED_ROM_SIZE=1048576

usage() {
    cat <<'EOF'
Usage: bash scripts/verify-rom-readonly.sh ROM_PATH [NEW_REPORT_DIRECTORY]

Run read-only inspection and source/ROM comparison commands. ROM bytes are
never modified. The report directory must not already exist; without it, a
fresh temporary directory is created.

The script stops before byte comparisons if the image is not exactly the
expected headerless 1 MiB size. A matching size is not proof of ROM provenance.
Comparison mismatches are recorded in individual reports and checks.tsv; the
script continues through later checks and exits nonzero if any check fails.

Reports include image inspection, self-diff, scalar-table checks (v1 and v2),
overworld hidden-item source/layout and byte checks, dungeon room pointers,
text dictionary pointers, and encoded text-message bytes.
EOF
}

fail() {
    printf 'verify-rom-readonly: %s\n' "$*" >&2
    exit 2
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    usage
    exit 0
fi
[[ "$#" -ge 1 && "$#" -le 2 ]] || { usage >&2; exit 2; }

ROM_PATH="$1"
if [[ "$ROM_PATH" != /* ]]; then
    ROM_PATH="$CALLER_DIR/$ROM_PATH"
fi
[[ -f "$ROM_PATH" && -r "$ROM_PATH" ]] || fail "ROM path is missing or unreadable: $ROM_PATH"
command -v uv >/dev/null 2>&1 || fail "uv is required; install dependencies with 'uv sync --extra dev'"

if [[ "$#" -eq 2 ]]; then
    REPORT_DIR="$2"
    if [[ "$REPORT_DIR" != /* ]]; then
        REPORT_DIR="$CALLER_DIR/$REPORT_DIR"
    fi
    [[ ! -e "$REPORT_DIR" && ! -L "$REPORT_DIR" ]] || fail "refusing to reuse an existing report directory: $REPORT_DIR"
    mkdir -p -- "$(dirname -- "$REPORT_DIR")" || fail "could not create parent directory for reports"
    mkdir -- "$REPORT_DIR" || fail "could not create report directory: $REPORT_DIR"
else
    REPORT_DIR="$(mktemp -d "${TMPDIR:-/tmp}/zelda-rom-checks.XXXXXX")" ||
        fail "could not create a temporary report directory"
fi

cd "$ROOT_DIR"
CLI=(uv run zelda-suite)
STATUS_FILE="$REPORT_DIR/checks.tsv"
printf 'check\texit_status\n' > "$STATUS_FILE"
FAILED=0

run_check() {
    local label="$1"
    local status=0
    shift
    printf '\n=== %s ===\n' "$label"
    if "$@"; then
        status=0
        printf 'PASS: %s\n' "$label"
    else
        status=$?
        FAILED=1
        printf 'CHECK FAILED (exit %s): %s — inspect the report/output above\n' "$status" "$label" >&2
    fi
    printf '%s\t%s\n' "$label" "$status" >> "$STATUS_FILE"
    return 0
}

printf 'ROM: %s\nReports: %s\n' "$ROM_PATH" "$REPORT_DIR"
run_check "inspect-rom" "${CLI[@]}" inspect-rom "$ROM_PATH" \
    --output "$REPORT_DIR/rom-inspection.json"

# Source-only reports are useful even before deciding whether byte checks can run.
run_check "inspect-overworld-hidden-items" "${CLI[@]}" inspect-overworld-hidden-items \
    --output "$REPORT_DIR/overworld-hidden-item-source-layout.json"
run_check "audit-overworld-hidden-item-value-semantics" "${CLI[@]}" \
    audit-overworld-hidden-item-value-semantics \
    --output "$REPORT_DIR/overworld-hidden-item-value-semantics.json"

ROM_SIZE="$(uv run python -c 'import os, sys; print(os.path.getsize(sys.argv[1]))' "$ROM_PATH")" ||
    fail "could not determine ROM size with the uv-managed Python"
if [[ "$ROM_SIZE" != "$EXPECTED_ROM_SIZE" ]]; then
    printf 'BLOCKED: expected a headerless 1 MiB ROM (%s bytes), got %s bytes. No ROM byte-comparison commands were run. See rom-inspection.json and source-only reports.\n' \
        "$EXPECTED_ROM_SIZE" "$ROM_SIZE" | tee "$REPORT_DIR/preflight.txt" >&2
    printf 'rom-size-preflight\t2\n' >> "$STATUS_FILE"
    exit 2
fi
printf 'ROM-size preflight: %s bytes (size only; provenance not established).\n' "$ROM_SIZE"

run_check "diff-rom-self-test" "${CLI[@]}" diff-rom "$ROM_PATH" "$ROM_PATH" \
    --output "$REPORT_DIR/self-diff.json"
run_check "verify-rom-tables-v1" "${CLI[@]}" verify-rom-tables "$ROM_PATH" \
    --output "$REPORT_DIR/scalar-table-verification.json"
run_check "verify-rom-tables-v2" "${CLI[@]}" verify-rom-tables "$ROM_PATH" \
    --include-skipped-expressions \
    --output "$REPORT_DIR/scalar-table-verification-v2.json"
run_check "verify-overworld-hidden-items" "${CLI[@]}" \
    verify-overworld-hidden-items "$ROM_PATH" \
    --output "$REPORT_DIR/overworld-hidden-item-verification.json"
run_check "verify-dungeon-room-pointers" "${CLI[@]}" \
    verify-dungeon-room-pointers "$ROM_PATH" \
    --output "$REPORT_DIR/dungeon-room-pointer-verification.json"
run_check "verify-text-dictionary-pointers" "${CLI[@]}" \
    verify-text-dictionary-pointers "$ROM_PATH" \
    --output "$REPORT_DIR/text-dictionary-pointer-verification.json"
run_check "verify-text-message-bytes" "${CLI[@]}" verify-text-message-bytes "$ROM_PATH" \
    --block reference/AsarUSALTTPDisassembly/Bank1C.asm Message_Data '$0E0000' '$0E7F29' \
    --block reference/AsarUSALTTPDisassembly/Bank0E.asm Message_DataExtra '$075F40' '$076E21' \
    --output "$REPORT_DIR/text-message-byte-verification.json"

printf '\nSummary: %s\n' "$STATUS_FILE"
cat "$STATUS_FILE"
printf '\nReports preserved in: %s\n' "$REPORT_DIR"
if (( FAILED != 0 )); then
    printf 'One or more checks returned nonzero. Review all JSON findings; failures do not establish ROM authenticity.\n' >&2
    exit 1
fi
printf 'All requested checks returned success. This still does not establish canonical ROM provenance or prove that untested semantics are correct.\n'
