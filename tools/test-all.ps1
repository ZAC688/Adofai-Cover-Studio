param([switch]$VisiblePerformanceTests)
$ErrorActionPreference = 'Stop'
$previousVisiblePerformance = $env:ADOFAI_VISIBLE_PERFORMANCE_TESTS
if ($VisiblePerformanceTests) { $env:ADOFAI_VISIBLE_PERFORMANCE_TESTS = '1' }
Push-Location (Split-Path -Parent $PSScriptRoot)
try {
    New-Item -ItemType Directory -Force -Path 'artifacts/final' | Out-Null
    $checkResults = @()
    foreach ($checkName in @('typecheck', 'lint', 'test', 'build')) {
        & node tools/npm/package/bin/npm-cli.js --prefix frontend run $checkName
        $checkResults += [pscustomobject]@{ Check = $checkName; ExitCode = $LASTEXITCODE }
    }
    & '.\.venv\Scripts\python.exe' -m pytest -v --junitxml=artifacts/final/all-tests.xml
    $checkResults += [pscustomobject]@{ Check = 'pytest-all'; ExitCode = $LASTEXITCODE }
    $checkResults | ConvertTo-Json | Set-Content -LiteralPath artifacts/final/check-results.json -Encoding UTF8
    $checkResults | Format-Table
    if (@($checkResults | Where-Object ExitCode -ne 0).Count -gt 0) { exit 1 }
} finally {
    $env:ADOFAI_VISIBLE_PERFORMANCE_TESTS = $previousVisiblePerformance
    Pop-Location
}
