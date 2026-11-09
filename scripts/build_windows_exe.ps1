# Build the Windows Lotus Beta executable with PyInstaller.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$venvPython = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "Run scripts\setup_windows.bat first."
    exit 1
}

& $venvPython -m pip install pyinstaller
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $venvPython -m PyInstaller --noconfirm --onefile --windowed --name "Lotus Beta" --icon "lotus\assets\lotus.ico" --add-data "lotus\assets;lotus\assets" run_lotus.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Copy-Item -Force "dist\Lotus Beta.exe" "Lotus Beta.exe"
Write-Host "Built Lotus Beta.exe"
