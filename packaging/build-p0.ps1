$ErrorActionPreference = 'Stop'
Push-Location (Split-Path -Parent $PSScriptRoot)
try {
    & '.\.venv\Scripts\python.exe' -m PyInstaller --noconfirm --clean --onedir --name adofai-p0 --paths . --add-data 'models/u2netp.onnx;models' experiments/p0_entry.py
    if ($LASTEXITCODE -ne 0) { throw 'P0 build failed' }
} finally {
    Pop-Location
}
