"""Deterministic, read-only byte-diff utilities.

This package compares byte buffers supplied by callers; it does not open ROM
files or write patches. File I/O belongs in the approved extract/write layers.
"""
from zelda_suite.diff.rom_diff import DiffRegion, ROMByteDiff, compare_bytes

__all__ = ["DiffRegion", "ROMByteDiff", "compare_bytes"]
