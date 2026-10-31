"""Tests for the ROM writer (src/zelda_suite/write/).

The base image is synthetic: 1 MiB with every chest and hidden-item record placed at its
source-derived offset with its source baseline bytes, so no real ROM is needed (CI is
ROM-independent). One test uses the local US image when it is present.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from click.testing import CliRunner

from zelda_suite.cli.main import cli
from zelda_suite.project.store import (
    create_custom_overworld_hidden_item,
    get_dungeon_chest_model,
    get_overworld_hidden_item_model,
    import_dungeon_chest_data,
    import_overworld_hidden_item_model,
    initialize_project,
    update_dungeon_chest_record,
    update_overworld_hidden_item,
)
from zelda_suite.write import BuildError, build_rom, lorom_checksum, plan_project_patches

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "data" / "extracted" / "manifest.json"
BANK1B = ROOT / "reference" / "AsarUSALTTPDisassembly" / "Bank1B.asm"
US_ROM = ROOT / "base_game_roms" / "Legend of Zelda, The - A Link to the Past (U) [!].smc"


@pytest.fixture
def project(tmp_path: Path) -> Path:
    if not BANK1B.is_file():
        pytest.skip("disassembly submodule not checked out")
    database, _ = initialize_project("rom_build", tmp_path)
    import_dungeon_chest_data(database, REGISTRY_PATH, dry_run=False)
    import_overworld_hidden_item_model(database, BANK1B, dry_run=False)
    return database


def _synthetic_base(database: Path, path: Path) -> Path:
    """A 1 MiB image holding every record's source baseline at its offset, with a valid header checksum."""
    image = bytearray(b"\xA5" * 0x100000)
    for e in get_dungeon_chest_model(database)["entries"]:
        o = e["candidate_entry_offset"]
        image[o:o + 3] = e["source_literal_value"].to_bytes(3, "little")
    for r in get_overworld_hidden_item_model(database)["records"]:
        o = r["source_file_offset"]
        image[o:o + 3] = r["source_coordinate_word"].to_bytes(2, "little") + bytes([r["source_value_byte"]])
    checksum, complement = lorom_checksum(image)
    image[0x7FDC:0x7FDE] = complement.to_bytes(2, "little")
    image[0x7FDE:0x7FE0] = checksum.to_bytes(2, "little")
    path.write_bytes(bytes(image))
    return path


def test_an_unedited_project_builds_the_base_image_unchanged(project: Path, tmp_path: Path) -> None:
    base = _synthetic_base(project, tmp_path / "base.sfc")
    report = build_rom(project, base, tmp_path / "out.sfc")
    assert report["patch_count"] == 0 and report["diff"]["changed_byte_count"] == 0
    assert report["output_sha256"] == hashlib.sha256(base.read_bytes()).hexdigest()


def test_a_dry_run_reports_the_patch_and_writes_nothing(project: Path, tmp_path: Path) -> None:
    base = _synthetic_base(project, tmp_path / "base.sfc")
    update_dungeon_chest_record(project, 26, item_value=0x46, dry_run=False)
    report = build_rom(project, base, tmp_path / "out.sfc")
    assert report["dry_run"] and not report["written"] and not (tmp_path / "out.sfc").exists()
    (patch,) = report["patches"]
    assert patch["offset_hex"] == "$00E9BC" and patch["old"] == "040112" and patch["new"] == "040146"
    assert patch["citation"]["source"].startswith("Bank01.asm:") and patch["citation"]["table_index"] == 26
    changed = {r["start_offset"] for r in report["diff"]["regions"]}
    assert 0xE9BE in changed and changed - {0xE9BE} <= set(range(0x7FDC, 0x7FE0))


def test_applying_writes_the_patched_image_with_a_valid_checksum(project: Path, tmp_path: Path) -> None:
    base = _synthetic_base(project, tmp_path / "base.sfc")
    update_dungeon_chest_record(project, 3, room_value=0x00A9, is_big_chest=True, dry_run=False)
    update_overworld_hidden_item(project, 0, coordinate_word=0x1234, value_byte=0x84, dry_run=False)
    report = build_rom(project, base, tmp_path / "out.sfc", dry_run=False)
    out = (tmp_path / "out.sfc").read_bytes()
    assert report["written"] and hashlib.sha256(out).hexdigest() == report["output_sha256"]
    assert report["patch_count"] == 2
    hidden = next(p for p in report["patches"] if p["domain"] == "overworld_hidden_item")
    assert out[hidden["offset"]:hidden["offset"] + 3] == bytes.fromhex("341284")
    checksum, complement = lorom_checksum(out)
    assert out[0x7FDE:0x7FE0] == checksum.to_bytes(2, "little")
    assert out[0x7FDC:0x7FDE] == complement.to_bytes(2, "little")
    assert base.read_bytes() != out                                     # the base is untouched …
    assert hashlib.sha256(base.read_bytes()).hexdigest() == report["base_sha256"]


def test_a_base_image_that_disagrees_with_the_source_baseline_is_refused(project: Path, tmp_path: Path) -> None:
    base = _synthetic_base(project, tmp_path / "base.sfc")
    image = bytearray(base.read_bytes())
    image[0xE9BE] ^= 0xFF                       # chest 26's item byte, as another ROM might hold it
    base.write_bytes(bytes(image))
    update_dungeon_chest_record(project, 26, item_value=0x46, dry_run=False)
    with pytest.raises(BuildError, match="not the image these offsets were verified on"):
        build_rom(project, base, tmp_path / "out.sfc", dry_run=False)
    assert not (tmp_path / "out.sfc").exists()


def test_project_authored_hidden_items_are_refused(project: Path, tmp_path: Path) -> None:
    base = _synthetic_base(project, tmp_path / "base.sfc")
    create_custom_overworld_hidden_item(project, area_indices=[12], coordinate_word=0x1234, value_byte=0x05,
                                        dry_run=False)
    with pytest.raises(BuildError, match="project-authored hidden item"):
        build_rom(project, base, tmp_path / "out.sfc")


def test_the_base_image_and_existing_files_are_never_overwritten(project: Path, tmp_path: Path) -> None:
    base = _synthetic_base(project, tmp_path / "base.sfc")
    before = base.read_bytes()
    with pytest.raises(BuildError, match="base image"):
        build_rom(project, base, base, dry_run=False)
    (tmp_path / "taken.sfc").write_bytes(b"x")
    with pytest.raises(BuildError, match="exists"):
        build_rom(project, base, tmp_path / "taken.sfc", dry_run=False)
    assert base.read_bytes() == before and (tmp_path / "taken.sfc").read_bytes() == b"x"
    build_rom(project, base, tmp_path / "taken.sfc", dry_run=False, overwrite=True)


def test_a_wrong_size_image_is_refused(project: Path, tmp_path: Path) -> None:
    base = tmp_path / "headered.sfc"
    base.write_bytes(b"\x00" * (0x100000 + 512))
    with pytest.raises(BuildError, match="1 MiB"):
        build_rom(project, base, tmp_path / "out.sfc")


def test_patches_are_ordered_and_cite_their_rows(project: Path) -> None:
    update_dungeon_chest_record(project, 100, item_value=0x01, dry_run=False)
    update_dungeon_chest_record(project, 5, item_value=0x01, dry_run=False)
    patches = plan_project_patches(project)
    assert [p.record for p in patches] == ["chest 5", "chest 100"]
    assert all(p.citation["source_revision"] for p in patches)


def test_the_checksum_routine_matches_the_us_image_when_present() -> None:
    if not US_ROM.is_file():
        pytest.skip("local US ROM not present (CI is ROM-independent)")
    rom = US_ROM.read_bytes()
    checksum, complement = lorom_checksum(rom)
    assert rom[0x7FDE:0x7FE0] == checksum.to_bytes(2, "little")
    assert rom[0x7FDC:0x7FDE] == complement.to_bytes(2, "little")


def test_the_cli_previews_then_applies(project: Path, tmp_path: Path) -> None:
    base = _synthetic_base(project, tmp_path / "base.sfc")
    update_dungeon_chest_record(project, 26, item_value=0x46, dry_run=False)
    runner = CliRunner()
    out = tmp_path / "hack.sfc"
    preview = runner.invoke(cli, ["build-rom", str(project), "--base-rom", str(base), "--output", str(out)])
    assert preview.exit_code == 0, preview.output
    assert '"dry_run": true' in preview.output and not out.exists()
    applied = runner.invoke(cli, ["build-rom", str(project), "--base-rom", str(base), "--output", str(out), "--apply"])
    assert applied.exit_code == 0, applied.output and out.is_file()
    refused = runner.invoke(cli, ["build-rom", str(project), "--base-rom", str(base), "--output", str(out), "--apply"])
    assert refused.exit_code != 0 and "exists" in refused.output
