"""Smoke tests for the bundled read-only ROM verification script."""
from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify-rom-readonly.sh"


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash is not available")
def test_readonly_rom_script_has_valid_shell_syntax() -> None:
    result = subprocess.run(
        ["bash", "-n", str(SCRIPT)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash is not available")
def test_readonly_rom_script_help_needs_no_rom_or_uv() -> None:
    result = subprocess.run(
        ["bash", str(SCRIPT), "--help"],
        check=False,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    assert result.returncode == 0, result.stderr
    assert "Usage: bash scripts/verify-rom-readonly.sh ROM_PATH" in result.stdout
    assert "ROM bytes are" in result.stdout
    assert "checks.tsv" in result.stdout


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash is not available")
def test_readonly_rom_script_rejects_missing_rom_argument() -> None:
    result = subprocess.run(
        ["bash", str(SCRIPT)],
        check=False,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    assert result.returncode == 2
    assert "Usage: bash scripts/verify-rom-readonly.sh ROM_PATH" in result.stderr
