$ErrorActionPreference = "Stop"
$serviceDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $serviceDir ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    & (Join-Path $serviceDir "setup.ps1")
}

Push-Location $serviceDir
try {
    & $python -m uvicorn app:app --host 127.0.0.1 --port 8010
}
finally {
    Pop-Location
}
