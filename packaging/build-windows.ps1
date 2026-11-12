param([string]$OutputRoot = 'dist/0.8.0', [string]$ArchiveName = 'ADOFAI-Cover-Studio-0.8.0-windows-x64.zip')
$ErrorActionPreference = 'Stop'
$appRoot = (Resolve-Path (Split-Path -Parent $PSScriptRoot)).Path
$appOutputRoot = [System.IO.Path]::GetFullPath((Join-Path $appRoot $OutputRoot))
$appOutput = Join-Path $appOutputRoot 'ADOFAI-Cover-Studio'
if (-not $appOutput.StartsWith($appRoot + '\', [System.StringComparison]::OrdinalIgnoreCase)) { throw 'Invalid build output path' }
if ([System.IO.Path]::GetFileName($ArchiveName) -ne $ArchiveName) { throw 'Invalid archive name' }
Push-Location $appRoot
try {
    $env:PYINSTALLER_CONFIG_DIR = Join-Path $appRoot 'tools\pyinstaller-cache'
    & node tools/npm/package/bin/npm-cli.js --prefix frontend run build
    if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed' }
    & '.\.venv\Scripts\python.exe' packaging/license_report.py
    if ($LASTEXITCODE -ne 0) { throw 'License collection failed' }
    # Resolve Windows ICU through System32. Foreign ICU DLLs on a developer's
    # PATH (for example Git/MSYS) export incompatible, version-suffixed symbols.
    $previousBuildPath = $env:PATH
    try {
        $env:PATH = $env:SystemRoot + '\System32;' + $env:SystemRoot
        & '.\.venv\Scripts\python.exe' -m PyInstaller --noconfirm --clean --onedir --windowed --icon 'frontend/public/app-icon.ico' --name ADOFAI-Cover-Studio --distpath $appOutputRoot --paths . --collect-submodules uvicorn --collect-submodules fontTools --add-data 'frontend/dist;frontend/dist' --add-data 'Logos;Logos' --add-data 'models/u2netp.onnx;models' --add-data 'packaging/dependency-notices;licenses' --add-data 'experiments/static_track_editor.html;experiments' backend/entry.py
    } finally { $env:PATH = $previousBuildPath }
    if ($LASTEXITCODE -ne 0) { throw 'Windows packaging failed' }
    Copy-Item -LiteralPath 'docs\使用说明.md' -Destination (Join-Path $appOutput '使用说明.md')
    Copy-Item -LiteralPath 'packaging\release-manifest.json' -Destination (Join-Path $appOutput 'release-manifest.json')
    New-Item -ItemType Directory -Force -Path 'release' | Out-Null
    $archivePath = Join-Path 'release' $ArchiveName
    Compress-Archive -LiteralPath $appOutput -DestinationPath $archivePath -Force
    $releaseHash = Get-FileHash -LiteralPath $archivePath -Algorithm SHA256
    ($releaseHash.Hash.ToLowerInvariant() + '  ' + $ArchiveName) | Set-Content -LiteralPath ($archivePath + '.sha256') -Encoding ASCII
    New-Item -ItemType Directory -Force -Path 'artifacts' | Out-Null
    @{ directory = $appOutput; archive = $archivePath } | ConvertTo-Json | Set-Content -LiteralPath 'artifacts/current-bundle.json' -Encoding UTF8
} finally {
    Pop-Location
}
