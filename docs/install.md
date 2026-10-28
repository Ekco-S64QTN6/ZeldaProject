# Install and initialize a workspace

The setup scripts prepare the Python environment, initialize a project, and
validate the resulting SQLite database and JSON sidecar. They work without a
game ROM and never download, copy, open, or modify one. Dependency installation
may access the configured Python package index.

## macOS and Linux

From a clone of ZeldaProject:

```bash
bash scripts/setup.sh --name my-hack
```

To place project files in another workspace directory:

```bash
bash scripts/setup.sh --name my-hack --workspace /path/to/workspace
```

The script prefers `uv` and runs `uv sync --extra dev`. If `uv` is not
installed, it falls back to Python 3.12 or newer, creates the repository's
`.venv`, and installs `.[dev]` into that environment.

## Windows PowerShell

From a clone of ZeldaProject:

```powershell
.\scripts\setup.ps1 -Name my-hack
```

To choose another workspace:

```powershell
.\scripts\setup.ps1 -Name my-hack -Workspace D:\ZeldaWorkspace
```

The PowerShell script has the same `uv` preference and Python virtual
environment fallback. If PowerShell blocks running local scripts, use the
organization's approved script policy rather than downloading a replacement
installer from an untrusted source.

## What setup changes

- Installs the project's Python runtime/development dependencies in the
  environment managed by `uv` or the repository-local `.venv`.
- Creates `project/NAME.db` and `project/NAME.json` under the selected
  workspace, then validates their consistency.
- Refuses to overwrite either of those files if they already exist.
- Does not fetch a ROM, install YAZE/Asar, or assert that external tools can
  read a ROM.

Run `uv run zelda-suite doctor` (or `just doctor`) separately after placing
an authorized, clean US ROM at the canonical local path. That check is
intentionally separate because it requires the ROM; it does not download or
modify it. See [the doctor guide](./doctor.md).

If setup reports that the project already exists, validate it with
`uv run zelda-suite validate project/NAME.db` rather than rerunning setup with
the same name. Choose another name to create a separate project.
