"""Read-only inspection and offset mapping for ROM images.

This is the only module in the current extraction package that opens a ROM
file. It hashes the bytes in memory and reports metadata; it never modifies,
copies, or writes the image.
"""
from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

EXPECTED_US_ROM_SIZE = 0x100000
COPIER_HEADER_SIZE = 0x200
LOROM_BANK_SIZE = 0x8000
LOROM_CPU_WINDOW_START = 0x8000


class ROMImageInspectionError(ValueError):
    """Raised when the ROM image cannot be read for inspection."""


def lorom_cpu_address(file_offset: int) -> int:
    """Map a headerless LoROM file offset to its canonical CPU address.

    The result uses the low-bank representation used in source declarations:
    file offset 0x058000 maps to CPU address 0x0B8000. SNES mirrors in banks
    0x80-0xFF are intentionally not emitted.
    """
    if isinstance(file_offset, bool) or not isinstance(file_offset, int):
        raise TypeError("file_offset must be an integer")
    if not 0 <= file_offset < EXPECTED_US_ROM_SIZE:
        raise ValueError(
            f"file_offset must be within a 1 MiB headerless image "
            f"(0..{EXPECTED_US_ROM_SIZE - 1:#x})"
        )
    bank = file_offset // LOROM_BANK_SIZE
    address = LOROM_CPU_WINDOW_START + file_offset % LOROM_BANK_SIZE
    return (bank << 16) | address


def format_lorom_cpu_address(file_offset: int) -> str:
    """Return the canonical six-hex-digit Asar-style LoROM address."""
    return f"${lorom_cpu_address(file_offset):06X}"


@dataclass(frozen=True, slots=True)
class ROMImageInspection:
    """Metadata and a headerless-size assessment for an inspected ROM image."""

    filename: str
    size_bytes: int
    sha256: str
    expected_headerless_size_bytes: int
    is_expected_headerless_size: bool
    header_assessment: str
    offset_map_applicable: bool
    first_cpu_address: str | None
    last_cpu_address: str | None

    def to_dict(self) -> dict[str, Any]:
        """Return stable JSON-friendly metadata."""
        payload = asdict(self)
        payload["format"] = "zelda-suite-rom-image"
        payload["format_version"] = 1
        payload["offset_map"] = {
            "mapping": "LoROM canonical low-bank representation",
            "bank_size_bytes": LOROM_BANK_SIZE,
            "cpu_window_start": f"${LOROM_CPU_WINDOW_START:04X}",
            "cpu_window_end": "$FFFF",
            "applicable": self.offset_map_applicable,
            "first_file_offset": 0 if self.offset_map_applicable else None,
            "last_file_offset": (
                self.size_bytes - 1 if self.offset_map_applicable else None
            ),
            "first_cpu_address": self.first_cpu_address,
            "last_cpu_address": self.last_cpu_address,
            "example_file_offset": 0x058000,
            "example_cpu_address": format_lorom_cpu_address(0x058000),
        }
        return payload


def inspect_rom_image(path: str | Path) -> ROMImageInspection:
    """Read and hash a ROM image without modifying it.

    Header assessment is based on size only. An exact 1 MiB size is consistent
    with a headerless US image, but does not prove the ROM's region or dump
    correctness. A size 512 bytes over an integral bank count is flagged as a
    likely copier header; all other sizes are reported as unrecognized.
    """
    image_path = Path(path)
    try:
        data = image_path.read_bytes()
    except (OSError, IsADirectoryError) as exc:
        raise ROMImageInspectionError(
            f"could not read ROM image {image_path}: {exc}"
        ) from exc

    size = len(data)
    is_headerless = size == EXPECTED_US_ROM_SIZE
    if is_headerless:
        assessment = "headerless-by-expected-size"
    elif size == EXPECTED_US_ROM_SIZE + COPIER_HEADER_SIZE or (
        size % LOROM_BANK_SIZE == COPIER_HEADER_SIZE
    ):
        assessment = "copier-header-suspected-by-size"
    else:
        assessment = "unrecognized-size"

    return ROMImageInspection(
        filename=image_path.name,
        size_bytes=size,
        sha256=hashlib.sha256(data).hexdigest(),
        expected_headerless_size_bytes=EXPECTED_US_ROM_SIZE,
        is_expected_headerless_size=is_headerless,
        header_assessment=assessment,
        offset_map_applicable=is_headerless,
        first_cpu_address=(
            format_lorom_cpu_address(0) if is_headerless else None
        ),
        last_cpu_address=(
            format_lorom_cpu_address(size - 1) if is_headerless else None
        ),
    )
