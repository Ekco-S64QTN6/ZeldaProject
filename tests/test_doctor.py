"""Tests for the Phase 0 doctor diagnostics."""
from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from zelda_suite.cli import main as main_module


def _make_sized_file(path: Path, size: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as file:
        file.truncate(size)


def test_inspect_base_rom_accepts_headerless_us_rom(tmp_path: Path) -> None:
    rom_path = tmp_path / "zelda.smc"
    _make_sized_file(rom_path, main_module.EXPECTED_US_ROM_SIZE)

    status, message = main_module._inspect_base_rom(rom_path)

    assert status == "OK"
    assert "headerless US ROM found" in message
    assert "1,048,576 bytes" in message


def test_inspect_base_rom_reports_missing_file(tmp_path: Path) -> None:
    status, message = main_module._inspect_base_rom(tmp_path / "missing.smc")

    assert status == "FAIL"
    assert "not found" in message


def test_inspect_base_rom_detects_512_byte_copier_header(tmp_path: Path) -> None:
    rom_path = tmp_path / "headered.smc"
    _make_sized_file(rom_path, main_module.EXPECTED_US_ROM_SIZE + 512)

    status, message = main_module._inspect_base_rom(rom_path)

    assert status == "FAIL"
    assert "512-byte copier header" in message
    assert "headerless" in message


def test_inspect_base_rom_rejects_unexpected_size(tmp_path: Path) -> None:
    rom_path = tmp_path / "truncated.smc"
    _make_sized_file(rom_path, 123)

    status, message = main_module._inspect_base_rom(rom_path)

    assert status == "FAIL"
    assert "unexpected ROM size" in message


def test_doctor_exits_nonzero_without_required_rom(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(main_module.shutil, "which", lambda _name: None)
    result = CliRunner().invoke(
        main_module.cli, ["doctor", "--workspace", str(tmp_path)]
    )

    assert result.exit_code == 1
    assert "[FAIL] Base ROM:" in result.output
    assert "[WARN] YAZE/z3ed CLI" in result.output
    assert "[WARN] z3cli agent harness" in result.output
    assert "do not commit them" in result.output


def test_doctor_passes_rom_check_and_warns_about_missing_tools(
    tmp_path: Path, monkeypatch
) -> None:
    rom_path = (
        tmp_path
        / "base_game_roms"
        / main_module.US_ROM_FILENAME
    )
    _make_sized_file(rom_path, main_module.EXPECTED_US_ROM_SIZE)
    monkeypatch.setattr(main_module.shutil, "which", lambda _name: None)

    result = CliRunner().invoke(
        main_module.cli, ["doctor", "--workspace", str(tmp_path)]
    )

    assert result.exit_code == 0
    assert "[OK] Base ROM:" in result.output
    assert "Base ROM check passed" in result.output
    assert "[WARN]" in result.output
