"""Smoke tests for the cross-platform workspace setup scripts."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SETUP_SCRIPT = ROOT / "scripts" / "setup.sh"


def test_setup_script_is_valid_bash() -> None:
    result = subprocess.run(
        ["bash", "-n", str(SETUP_SCRIPT)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_setup_script_uses_uv_without_requesting_rom_access(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    log_path = tmp_path / "commands.log"
    fake_uv = fake_bin / "uv"
    fake_uv.write_text(
        "#!/usr/bin/env bash\n"
        'printf "%s\\n" "$*" >> "$SETUP_TEST_LOG"\n',
        encoding="utf-8",
    )
    fake_uv.chmod(0o755)

    workspace = tmp_path / "workspace"
    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
    env["SETUP_TEST_LOG"] = str(log_path)

    result = subprocess.run(
        [
            "bash",
            str(SETUP_SCRIPT),
            "--name",
            "smoke-test",
            "--workspace",
            str(workspace),
        ],
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    commands = log_path.read_text(encoding="utf-8").splitlines()
    assert commands == [
        "sync --extra dev",
        "run zelda-suite --help",
        f"run zelda-suite init smoke-test --workspace {workspace}",
        f"run zelda-suite validate {workspace / 'project' / 'smoke-test.db'}",
    ]
    assert "No ROM was fetched or modified" in result.stdout
    assert not any("doctor" in command or ".smc" in command for command in commands)


def test_setup_script_refuses_to_overwrite_existing_project(tmp_path: Path) -> None:
    project_dir = tmp_path / "workspace" / "project"
    project_dir.mkdir(parents=True)
    existing_db = project_dir / "smoke-test.db"
    existing_db.write_text("do not overwrite", encoding="utf-8")
    result = subprocess.run(
        [
            "bash",
            str(SETUP_SCRIPT),
            "--name",
            "smoke-test",
            "--workspace",
            str(project_dir.parent),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "refusing to overwrite an existing project" in result.stderr
    assert existing_db.read_text(encoding="utf-8") == "do not overwrite"
