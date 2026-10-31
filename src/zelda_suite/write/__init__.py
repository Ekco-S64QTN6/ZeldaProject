"""The ROM writer: project edits to a new ROM file, dry-run first.

This is the only package that produces ROM bytes (CLAUDE.md §7 rule 1). It reads the
base image through the extraction layer, never modifies it, and writes a separate
output file only when explicitly applied.
"""
from zelda_suite.write.rom_build import (
    BuildError,
    BuildPatch,
    build_rom,
    lorom_checksum,
    plan_project_patches,
)

__all__ = ["BuildError", "BuildPatch", "build_rom", "lorom_checksum", "plan_project_patches"]
