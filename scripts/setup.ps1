param(
    [string]$Name = "my-hack",
    [string]$Workspace = (Join-Path $PSScriptRoot "..")
)

$ErrorActionPreference = "Stop"
$Root = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$Workspace = [System.IO.Path]::GetFullPath($Workspace)

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)][string]$Executable,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed: $Executable $($Arguments -join ' ')"
    }
}

if ($Name -cnotmatch '^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$') {
    throw "Project name must be 1-64 characters and use letters, digits, '-' or '_'."
}

$ProjectDir = Join-Path $Workspace "project"
$Database = Join-Path $ProjectDir "$Name.db"
$JsonExport = Join-Path $ProjectDir "$Name.json"
if ((Test-Path $Database) -or (Test-Path $JsonExport)) {
    throw "Refusing to overwrite an existing project: $Database or $JsonExport"
}

New-Item -ItemType Directory -Force -Path $Workspace | Out-Null

$Uv = Get-Command uv -ErrorAction SilentlyContinue
if ($null -ne $Uv) {
    Push-Location $Root
    try {
        Invoke-Checked -Executable $Uv.Source -Arguments @("sync", "--extra", "dev")
    }
    finally {
        Pop-Location
    }
    $CliExecutable = $Uv.Source
    $CliPrefix = @("run", "zelda-suite")
}
else {
    $Venv = Join-Path $Root ".venv"
    $VenvPython = Join-Path $Root ".venv/Scripts/python.exe"
    if (-not (Test-Path $VenvPython)) {
        $Python = Get-Command python -ErrorAction SilentlyContinue
        $UsePython = $false
        if ($null -ne $Python) {
            $VersionText = & $Python.Source -c "import sys; print('%d.%d' % sys.version_info[:2])"
            $UsePython = ($LASTEXITCODE -eq 0 -and $VersionText -match '^3\.(\d+)$' -and [int]$Matches[1] -ge 12)
        }

        if ($UsePython) {
            Invoke-Checked -Executable $Python.Source -Arguments @("-m", "venv", $Venv)
        }
        else {
            $PythonLauncher = Get-Command py -ErrorAction SilentlyContinue
            if ($null -eq $PythonLauncher) {
                throw "uv or Python 3.12+ is required to prepare the environment."
            }
            Invoke-Checked -Executable $PythonLauncher.Source -Arguments @("-3.12", "-m", "venv", $Venv)
        }
    }

    if (-not (Test-Path $VenvPython)) {
        throw "Could not create the project-local Python 3.12+ virtual environment."
    }
    $VenvVersion = & $VenvPython -c "import sys; print('%d.%d' % sys.version_info[:2])"
    if ($LASTEXITCODE -ne 0 -or $VenvVersion -notmatch '^3\.(\d+)$' -or [int]$Matches[1] -lt 12) {
        throw "The existing .venv must use Python 3.12+; remove it or install with uv."
    }
    $VenvCli = Join-Path $Root ".venv/Scripts/zelda-suite.exe"
    Invoke-Checked -Executable $VenvPython -Arguments @("-m", "pip", "install", "--upgrade", "pip")
    Push-Location $Root
    try {
        Invoke-Checked -Executable $VenvPython -Arguments @("-m", "pip", "install", "-e", ".[dev]")
    }
    finally {
        Pop-Location
    }
    if (-not (Test-Path $VenvCli)) {
        throw "Installation did not create $VenvCli"
    }
    $CliExecutable = $VenvCli
    $CliPrefix = @()
}

New-Item -ItemType Directory -Force -Path $Workspace | Out-Null
Invoke-Checked -Executable $CliExecutable -Arguments ($CliPrefix + @("--help"))
Invoke-Checked -Executable $CliExecutable -Arguments ($CliPrefix + @("init", $Name, "--workspace", $Workspace))
Invoke-Checked -Executable $CliExecutable -Arguments ($CliPrefix + @("validate", $Database))

Write-Host ""
Write-Host "Setup complete. Project: $Database"
Write-Host "No ROM was fetched or modified. ROM-dependent checks are optional; see docs/doctor.md."
