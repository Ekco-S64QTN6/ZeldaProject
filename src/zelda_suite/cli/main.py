"""Entry point for the `zelda-suite` CLI."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import click

from zelda_suite import __version__
from zelda_suite.extract import parse_dl_pointer_table
from zelda_suite.project import initialize_project, validate_project
from zelda_suite.project.store import BASE_ROM_FILENAME

US_ROM_FILENAME = BASE_ROM_FILENAME
EXPECTED_US_ROM_SIZE = 1_048_576
COPIER_HEADER_SIZE = 512
SNES_ROM_BANK_SIZE = 0x8000

TOOL_CHECKS = (
    ("z3ed", "YAZE/z3ed CLI"),
    ("z3cli", "z3cli agent harness"),
)


def _inspect_base_rom(path: Path) -> tuple[str, str]:
    """Check the canonical ROM path and its expected headerless file size.

    This intentionally inspects filesystem metadata only; ROM bytes are read
    exclusively by future extraction/writing modules.
    """
    try:
        if not path.is_file():
            return "FAIL", f"not found: {path}"
        size = path.stat().st_size
    except OSError as exc:
        return "FAIL", f"could not inspect {path}: {exc}"

    if size == EXPECTED_US_ROM_SIZE:
        return "OK", f"headerless US ROM found ({size:,} bytes): {path}"

    if size == EXPECTED_US_ROM_SIZE + COPIER_HEADER_SIZE:
        return (
            "FAIL",
            "ROM appears to include a 512-byte copier header "
            f"({size:,} bytes); expected a headerless file "
            f"({EXPECTED_US_ROM_SIZE:,} bytes).",
        )

    if size % SNES_ROM_BANK_SIZE == COPIER_HEADER_SIZE:
        return (
            "FAIL",
            f"file size ({size:,} bytes) has a 512-byte copier-header offset; "
            "expected the clean, headerless US ROM.",
        )

    return (
        "FAIL",
        f"unexpected ROM size ({size:,} bytes); expected exactly "
        f"{EXPECTED_US_ROM_SIZE:,} bytes for the headerless US ROM.",
    )


@click.group()
@click.version_option(__version__)
def cli() -> None:
    """ZeldaProject authoring suite."""





def _parse_offset_text(value: str) -> int:
    """Parse a decimal, 0x-prefixed, or Asar-style $-prefixed offset."""
    try:
        if value.startswith("$"):
            return int(value[1:], 16)
        return int(value, 0)
    except ValueError as exc:
        raise click.BadParameter(
            "use a decimal, 0x-prefixed, or Asar-style $-prefixed integer"
        ) from exc


@cli.command(name="inspect-pointer-table")
@click.argument(
    "source",
    type=click.Path(path_type=Path, exists=True, file_okay=True, dir_okay=False),
)
@click.argument("label")
@click.option(
    "--table-offset",
    required=True,
    help="Verified file offset of the first pointer entry (e.g. $0F8000).",
)
@click.option(
    "--entry-width",
    type=click.IntRange(min=1),
    default=3,
    show_default=True,
    help="Bytes per source-table entry.",
)
@click.option(
    "--source-revision",
    default=None,
    show_default=False,
    help="Revision to record; omitted values are marked unspecified.",
)
@click.option(
    "--output",
    type=click.Path(path_type=Path, exists=False, file_okay=True, dir_okay=False),
    default=None,
    help="Write JSON to a new file instead of stdout; existing files are preserved.",
)
def inspect_pointer_table(
    source: Path,
    label: str,
    table_offset: str,
    entry_width: int,
    source_revision: str | None,
    output: Path | None,
) -> None:
    """Parse a source-level Asar dl table to auditable JSON records.

    This command parses assembly text only. It does not read ROM bytes or
    resolve symbols to target offsets.
    """
    try:
        offset = _parse_offset_text(table_offset)
        source_text = source.read_text(encoding="utf-8")
        recorded_revision = source_revision or "unspecified"
        entries = parse_dl_pointer_table(
            source_text,
            label,
            offset,
            entry_width=entry_width,
            source_revision=recorded_revision,
        )
    except (OSError, UnicodeError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    payload = {
        "format": "zelda-suite-pointer-table",
        "format_version": 1,
        "source_file": source.name,
        "source_revision": recorded_revision,
        "table_label": label,
        "table_file_offset": offset,
        "entry_width": entry_width,
        "entry_count": len(entries),
        "entries": [entry.to_dict() for entry in entries],
    }
    rendered = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"

    if output is None:
        click.echo(rendered, nl=False)
        return

    try:
        with output.open("x", encoding="utf-8", newline="\n") as output_file:
            output_file.write(rendered)
    except FileExistsError as exc:
        raise click.ClickException(
            f"refusing to overwrite existing output: {output}"
        ) from exc
    except OSError as exc:
        raise click.ClickException(f"could not write {output}: {exc}") from exc

    click.echo(f"Wrote {len(entries)} pointer-table entries to {output}")

@cli.command(name="init")
@click.argument("name")
@click.option(
    "--workspace",
    type=click.Path(path_type=Path, exists=True, file_okay=False, dir_okay=True),
    default=".",
    show_default=True,
    help="Workspace root; project files are created in workspace/project/.",
)
def init_project(name: str, workspace: Path) -> None:
    """Initialize a versioned SQLite project and its JSON export."""
    try:
        database_path, json_path = initialize_project(name, workspace / "project")
    except (ValueError, FileExistsError, OSError) as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(f"Created SQLite project: {database_path}")
    click.echo(f"Created JSON export:    {json_path}")
    click.echo("No ROM was read or copied. Game-system schemas will be added in Phase 1.")


@cli.command(name="validate")
@click.argument(
    "database",
    type=click.Path(path_type=Path, exists=False, file_okay=True, dir_okay=False),
)
@click.option(
    "--json",
    "json_path",
    type=click.Path(path_type=Path, exists=False, file_okay=True, dir_okay=False),
    default=None,
    help="JSON export path (defaults to the database path with a .json suffix).",
)
def validate(database: Path, json_path: Path | None) -> None:
    """Validate a project's SQLite database and its JSON export without changing either."""
    problems = validate_project(database, json_path)
    if problems:
        for problem in problems:
            click.echo(f"[FAIL] {problem}", err=True)
        raise click.exceptions.Exit(1)

    click.echo(f"[OK] SQLite project and JSON export are consistent: {database}")


@cli.command()
@click.option(
    "--workspace",
    type=click.Path(path_type=Path, exists=True, file_okay=False, dir_okay=True),
    default=".",
    show_default=True,
    help="Workspace root containing base_game_roms/.",
)
def doctor(workspace: Path) -> None:
    """Check the base ROM and report whether Phase 0 tools are on PATH."""
    rom_path = workspace / "base_game_roms" / US_ROM_FILENAME
    status, message = _inspect_base_rom(rom_path)
    click.echo(f"[{status}] Base ROM: {message}")

    rom_check_failed = status != "OK"
    for executable, label in TOOL_CHECKS:
        location = shutil.which(executable)
        if location:
            click.echo(f"[OK] {label}: {location}")
        else:
            click.echo(f"[WARN] {label}: {executable!r} not found on PATH.")

    click.echo(
        "Note: tool checks only verify PATH visibility; they do not run the tools "
        "or prove ROM compatibility."
    )

    if rom_check_failed:
        click.echo(
            "Place a clean, headerless US dump at the path shown above. "
            "Keep ROM files local and do not commit them."
        )
        raise click.exceptions.Exit(1)

    click.echo("Base ROM check passed. Tool warnings are advisory during setup.")
