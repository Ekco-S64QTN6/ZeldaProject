"""Entry point for the `zelda-suite` CLI."""
from __future__ import annotations

import click

from zelda_suite import __version__


@click.group()
@click.version_option(__version__)
def cli() -> None:
    """ZeldaProject authoring suite."""


@cli.command()
def doctor() -> None:
    """Check that the toolchain and ROMs are in place."""
    click.echo("Doctor not implemented yet — Day 0 stub.")
