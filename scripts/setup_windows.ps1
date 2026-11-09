# Lotus beta setup for Windows. Creates .venv and installs requirements.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$pythonExe = $null
$pythonArgs = @()
foreach ($version in @("3.14", "3.13", "3.12", "3.11")) {
    & py -$version --version *> $null
    if ($LASTEXITCODE -eq 0) {
        $pythonExe = "py"
        $pythonArgs = @("-$version")
        break
    }
}
if (-not $pythonExe) {
    & python --version *> $null
    if ($LASTEXITCODE -eq 0) {
        $pythonExe = "python"
        $pythonArgs = @()
    }
}
if (-not $pythonExe) {
    Write-Host "Python 3.11 or newer was not found. Install Python from https://www.python.org/downloads/ and retry."
    exit 1
}

Write-Host "Using Python: $pythonExe $($pythonArgs -join ' ')"
& $pythonExe @pythonArgs -m venv .venv
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$venvPython = Join-Path $root ".venv\Scripts\python.exe"
& $venvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $venvPython -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "Lotus setup complete. Run Run-Lotus.bat to start the app."
