param(
    [switch]$OneFile
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
$iconPath = Join-Path $projectRoot "assets\secure_journal.ico"
$versionFile = Join-Path $projectRoot "version_info.txt"

if (-not (Test-Path $python)) {
    throw "Python virtual environment not found at .venv. Create it first and install dependencies."
}
if (-not (Test-Path $iconPath)) {
    throw "Icon file not found at assets\\secure_journal.ico"
}
if (-not (Test-Path $versionFile)) {
    throw "Version metadata file not found at version_info.txt"
}

Push-Location $projectRoot
try {
    & $python -m pip install -r requirements.txt
    & $python -m pip install -r requirements-packaging.txt

    $modeArgs = @("--onedir")
    if ($OneFile) {
        $modeArgs = @("--onefile")
    }

    $pyInstallerArgs = @(
        "--noconfirm",
        "--windowed",
        "--name", "SecureJournal",
        "--collect-all", "customtkinter",
        "--icon", $iconPath,
        "--version-file", $versionFile
    ) + $modeArgs + @("secure_journal_app.py")

    & $python -m PyInstaller @pyInstallerArgs
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller build failed with exit code $LASTEXITCODE. Close any running SecureJournal.exe and retry."
    }

    Write-Host "Build complete. Output is in .\dist\SecureJournal\ (or .\dist\SecureJournal.exe with -OneFile)."
}
finally {
    Pop-Location
}
