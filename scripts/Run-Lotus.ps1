# Lotus beta launcher. Prefers the local virtualenv, then a supported Python 3.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$venvPython = Join-Path $root ".venv\Scripts\python.exe"
if (Test-Path $venvPython) {
    & $venvPython -m lotus
    exit $LASTEXITCODE
}

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
    Write-Host "Python 3.11 or newer was not found. Run scripts\setup_windows.bat first."
    exit 1
}

& $pythonExe @pythonArgs -m lotus
exit $LASTEXITCODE
