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

def test_setup_script_uses_python_fallback_without_uv_or_rom(tmp_path: Path) -> None:
    import shutil

    repository = tmp_path / "repository"
    scripts_dir = repository / "scripts"
    scripts_dir.mkdir(parents=True)
    fallback_script = scripts_dir / "setup.sh"
    shutil.copyfile(SETUP_SCRIPT, fallback_script)

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    log_path = tmp_path / "commands.log"
    fake_python = fake_bin / "python3"
    fake_python.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
printf 'python3 %s\\n' "$*" >> "$SETUP_TEST_LOG"
if [[ "${1:-}" == "-c" ]]; then
    exit 0
fi
if [[ "${1:-}" == "-m" && "${2:-}" == "venv" ]]; then
    venv="$3"
    mkdir -p "$venv/bin"
    cat > "$venv/bin/python" <<'PYTHON'
#!/usr/bin/env bash
set -euo pipefail
printf 'venv-python %s\\n' "$*" >> "$SETUP_TEST_LOG"
if [[ "${1:-}" == "-c" ]]; then
    exit 0
fi
if [[ "${1:-}" == "-m" && "${2:-}" == "pip" ]]; then
    if [[ "${3:-}" == "install" && "${4:-}" == "-e" ]]; then
        cat > "$(dirname "$0")/zelda-suite" <<'CLI'
#!/usr/bin/env bash
set -euo pipefail
printf 'cli %s\\n' "$*" >> "$SETUP_TEST_LOG"
case "${1:-}" in
    init)
        name="$2"
        workspace="$4"
        mkdir -p "$workspace/project"
        : > "$workspace/project/$name.db"
        : > "$workspace/project/$name.json"
        ;;
    validate)
        test -f "$2"
        ;;
esac
CLI
        chmod +x "$(dirname "$0")/zelda-suite"
    fi
    exit 0
fi
exit 0
PYTHON
    chmod +x "$venv/bin/python"
fi
""",
        encoding="utf-8",
    )
    fake_python.chmod(0o755)

    # Isolate PATH so an ambient system-wide uv cannot divert this test
    # away from the Python fallback branch. Keep only the commands the fake
    # setup environment needs, plus the fake Python executable above.
    fallback_tools = tmp_path / "fallback-tools"
    fallback_tools.mkdir()
    for tool in ("bash", "cat", "chmod", "dirname", "env", "mkdir"):
        executable = shutil.which(tool)
        assert executable is not None, f"test prerequisite not found: {tool}"
        (fallback_tools / tool).symlink_to(executable)

    workspace = tmp_path / "workspace"
    env = os.environ.copy()
    env["PATH"] = os.pathsep.join((str(fake_bin), str(fallback_tools)))
    env["SETUP_TEST_LOG"] = str(log_path)

    result = subprocess.run(
        [
            "bash",
            str(fallback_script),
            "--name",
            "fallback-test",
            "--workspace",
            str(workspace),
        ],
        cwd=repository,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    commands = log_path.read_text(encoding="utf-8").splitlines()
    assert any(command.startswith("python3 -m venv ") for command in commands)
    assert "venv-python -m pip install --upgrade pip" in commands
    assert "venv-python -m pip install -e .[dev]" in commands
    assert "cli --help" in commands
    assert (
        f"cli init fallback-test --workspace {workspace}" in commands
    )
    assert f"cli validate {workspace / 'project' / 'fallback-test.db'}" in commands
    assert (workspace / "project" / "fallback-test.db").is_file()
    assert (workspace / "project" / "fallback-test.json").is_file()
    assert "No ROM was fetched or modified" in result.stdout
    assert not any(command.startswith("uv ") for command in commands)
    assert not any("doctor" in command or ".smc" in command for command in commands)
