$ErrorActionPreference = "Stop"
$serviceDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvDir = Join-Path $serviceDir ".venv"
$python = Join-Path $venvDir "Scripts\python.exe"

if (-not (Test-Path $python)) {
    py -3.11 -m venv $venvDir
}

& $python -m pip install --disable-pip-version-check --upgrade pip
& $python -m pip install --disable-pip-version-check torch torchvision --index-url https://download.pytorch.org/whl/cpu
& $python -m pip install --disable-pip-version-check -r (Join-Path $serviceDir "requirements.txt")

Write-Host "CPU vision environment is ready. Models remain in the project models/ directory."
