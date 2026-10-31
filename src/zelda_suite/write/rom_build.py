"""Build a ROM from a project: in-place byte patches for edited records.

Supported domains are the two whose record offsets are proven against the US image:

- **Dungeon chests** (`Dungeon_ChestData`, Bank01): 168 packed 24-bit little-endian
  records at their source-derived offsets `$00E96E–$00EB65`. All 168 source literals
  matched the user's fingerprint-matched US ROM byte-for-byte on 2026-10-31.
- **Overworld hidden items** (Bank1B): each imported record is a little-endian
  coordinate word followed by a value byte at its declaration-stream offset; the
  read-only `verify-overworld-hidden-items` check matched all 550 comparisons.

Every patch is an in-place replacement of a fixed-size record. A build refuses when:

- the base image is not 1 MiB (the US headerless size these offsets assume);
- any patch's *source baseline* bytes differ from the base image at its offset —
  a different ROM, a different revision, or an offset this module has wrong;
- a patch falls outside its domain's table or overlaps another;
- the project holds project-authored hidden items (they need the table to grow,
  which an in-place patch cannot do — relocation is future work).

The SNES header checksum (`$7FDC` complement, `$7FDE` checksum, LoROM) is
recomputed over the patched image. The default is a dry run: the full report —
patches with their source citations, the byte diff, and both SHA-256s — is
produced without writing anything. With `dry_run=False` the result is written to
`output_path`, never over the base image, and never over an existing file unless
`overwrite=True`.
"""
from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from zelda_suite.diff.rom_diff import compare_bytes
from zelda_suite.extract.overworld_hidden_item_verification import DATA_END_EXCLUSIVE, DATA_START_OFFSET
from zelda_suite.extract.rom_image import read_rom_bytes
from zelda_suite.project import store

BUILD_REPORT_FORMAT = "zelda-suite-rom-build"
BUILD_REPORT_VERSION = 1
US_ROM_SIZE = 0x100000
HEADER_COMPLEMENT_OFFSET = 0x7FDC
HEADER_CHECKSUM_OFFSET = 0x7FDE

CHEST_TABLE = (0x00E96E, 0x00EB66)               # [start, end) of Dungeon_ChestData


class BuildError(ValueError):
    """The project cannot be built onto this base image; nothing was written."""


@dataclass(frozen=True)
class BuildPatch:
    """One record's bytes, before and after, and where the change comes from."""

    domain: str
    record: str
    offset: int
    old: bytes
    new: bytes
    citation: dict[str, Any] = field(default_factory=dict)

    @property
    def end(self) -> int:
        return self.offset + len(self.new)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["offset_hex"] = f"${self.offset:06X}"
        d["old"] = self.old.hex().upper()
        d["new"] = self.new.hex().upper()
        return d


def lorom_checksum(image: bytes | bytearray) -> tuple[int, int]:
    """(checksum, complement) for a 1 MiB LoROM image, computed as the SNES
    header defines it: the 16-bit sum of every byte with the four checksum bytes
    taken as FF FF 00 00. Verified against the US image (stored $AF0D)."""
    if len(image) != US_ROM_SIZE:
        raise BuildError(f"checksum is defined here for a {US_ROM_SIZE}-byte image, not {len(image)}")
    total = sum(image) - sum(image[HEADER_COMPLEMENT_OFFSET:HEADER_CHECKSUM_OFFSET + 2]) + 0xFF + 0xFF
    checksum = total & 0xFFFF
    return checksum, checksum ^ 0xFFFF


def plan_project_patches(database_path: str | Path) -> list[BuildPatch]:
    """The patches a project's edits make, ordered by offset. Reads the project only."""
    patches: list[BuildPatch] = []
    chests = store.get_dungeon_chest_model(database_path)
    if chests:
        for e in chests["entries"]:
            if not e["is_modified"]:
                continue
            patches.append(BuildPatch(
                domain="dungeon_chest",
                record=f"chest {e['table_index']}",
                offset=int(e["candidate_entry_offset"]),
                old=int(e["source_literal_value"]).to_bytes(3, "little"),
                new=int(e["literal_value"]).to_bytes(3, "little"),
                citation={
                    "project_table": "dungeon_chest_record",
                    "table_index": e["table_index"],
                    "source": f"{chests['source_file']}:{e['source_line']} Dungeon_ChestData",
                    "source_revision": e["source_revision"],
                    "source_literal": e["source_literal_hex"],
                    "literal": e["literal_hex"],
                    "fields": {"item_value": [e["source_item_value"], e["item_value"]],
                               "room_value": [e["source_room_value"], e["room_value"]],
                               "is_big_chest": [e["source_is_big_chest"], e["is_big_chest"]]},
                },
            ))
    hidden = store.get_overworld_hidden_item_model(database_path)
    if hidden:
        if hidden.get("custom_records"):
            raise BuildError(
                f"the project has {len(hidden['custom_records'])} project-authored hidden item(s); "
                "adding records needs the Bank1B table to grow, which this in-place writer cannot do "
                "(relocation is future work). Delete them or build from a copy without them.")
        for r in hidden["records"]:
            if not r["is_modified"]:
                continue
            patches.append(BuildPatch(
                domain="overworld_hidden_item",
                record=f"hidden item {r['record_index']}",
                offset=int(r["source_file_offset"]),
                old=int(r["source_coordinate_word"]).to_bytes(2, "little") + bytes([int(r["source_value_byte"])]),
                new=int(r["coordinate_word"]).to_bytes(2, "little") + bytes([int(r["value_byte"])]),
                citation={
                    "project_table": "overworld_hidden_item_record",
                    "record_index": r["record_index"],
                    "source": f"{hidden['source_file']}:{r['source_line']} {r['source_label']}",
                    "source_revision": hidden["source_revision"],
                    "area_indices": r["area_indices"],
                    "fields": {"coordinate_word": [r["source_coordinate_word_hex"], r["coordinate_word_hex"]],
                               "value_byte": [r["source_value_hex"], r["value_hex"]]},
                },
            ))
    return sorted(patches, key=lambda p: p.offset)


def _check(patches: list[BuildPatch], base: bytes) -> None:
    if len(base) != US_ROM_SIZE:
        raise BuildError(f"base image is {len(base)} bytes; the supported US image is headerless 1 MiB "
                         f"({US_ROM_SIZE} bytes)")
    # The hidden-item data region is the verified declaration-stream layout of Bank1B.
    bounds = {"dungeon_chest": CHEST_TABLE, "overworld_hidden_item": (DATA_START_OFFSET, DATA_END_EXCLUSIVE)}
    previous: BuildPatch | None = None
    for p in patches:
        lo, hi = bounds[p.domain]
        if len(p.old) != len(p.new):
            raise BuildError(f"{p.record}: a patch must keep its size ({len(p.old)} -> {len(p.new)} bytes)")
        if not (lo <= p.offset and p.end <= hi):
            raise BuildError(f"{p.record}: ${p.offset:06X}-${p.end:06X} is outside its table ${lo:06X}-${hi:06X}")
        if previous and p.offset < previous.end:
            raise BuildError(f"{p.record} overlaps {previous.record} at ${p.offset:06X}")
        actual = base[p.offset:p.end]
        if actual != p.old:
            raise BuildError(
                f"{p.record}: the base image holds {actual.hex().upper()} at ${p.offset:06X}, the source baseline "
                f"is {p.old.hex().upper()} — not the image these offsets were verified on")
        previous = p


def build_rom(database_path: str | Path, base_rom_path: str | Path, output_path: str | Path | None = None, *,
              dry_run: bool = True, overwrite: bool = False) -> dict[str, Any]:
    """Plan, check and (with dry_run=False) write a ROM. Returns the build report."""
    base_path = Path(base_rom_path)
    base = read_rom_bytes(base_path)
    patches = plan_project_patches(database_path)
    _check(patches, base)

    image = bytearray(base)
    for p in patches:
        image[p.offset:p.end] = p.new
    old_sum = (int.from_bytes(base[HEADER_CHECKSUM_OFFSET:HEADER_CHECKSUM_OFFSET + 2], "little"),
               int.from_bytes(base[HEADER_COMPLEMENT_OFFSET:HEADER_COMPLEMENT_OFFSET + 2], "little"))
    checksum, complement = lorom_checksum(image)
    image[HEADER_COMPLEMENT_OFFSET:HEADER_COMPLEMENT_OFFSET + 2] = complement.to_bytes(2, "little")
    image[HEADER_CHECKSUM_OFFSET:HEADER_CHECKSUM_OFFSET + 2] = checksum.to_bytes(2, "little")
    built = bytes(image)
    diff = compare_bytes(base, built)

    expected_regions = {(p.offset, p.end) for p in patches}
    for region in diff.regions:
        inside = any(lo <= region.start_offset and region.end_offset_exclusive <= hi for lo, hi in expected_regions)
        header = HEADER_COMPLEMENT_OFFSET <= region.start_offset and region.end_offset_exclusive <= HEADER_CHECKSUM_OFFSET + 2
        if not (inside or header):
            raise BuildError(f"internal: a byte changed outside every patch at ${region.start_offset:06X}")

    report: dict[str, Any] = {
        "format": BUILD_REPORT_FORMAT,
        "format_version": BUILD_REPORT_VERSION,
        "dry_run": dry_run,
        "project": str(database_path),
        "base_rom": str(base_path),
        "base_sha256": hashlib.sha256(base).hexdigest(),
        "output": str(output_path) if output_path else None,
        "output_sha256": hashlib.sha256(built).hexdigest(),
        "patch_count": len(patches),
        "patches": [p.to_dict() for p in patches],
        "header_checksum": {"before": f"${old_sum[0]:04X}/${old_sum[1]:04X}",
                            "after": f"${checksum:04X}/${complement:04X}"},
        "diff": diff.to_dict(),
        "written": False,
    }
    if dry_run:
        return report
    if output_path is None:
        raise BuildError("an output path is required to write")
    out = Path(output_path)
    if out.resolve() == base_path.resolve():
        raise BuildError("refusing to write over the base image")
    if out.exists() and not overwrite:
        raise BuildError(f"{out} exists; pass overwrite to replace it")
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + ".partial")
    tmp.write_bytes(built)
    tmp.replace(out)
    if hashlib.sha256(out.read_bytes()).hexdigest() != report["output_sha256"]:
        raise BuildError(f"{out} does not hold what was built")
    report["written"] = True
    return report
