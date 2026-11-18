param([ValidateSet('assembleDebug','assembleRelease','assembleDebugAndroidTest','connectedDebugAndroidTest','testDebugUnitTest','lintDebug')][string]$Task='assembleDebug')
$ErrorActionPreference='Stop'
$projectRoot=Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot
try {
    $javaCandidates=@($env:ADOFAI_JAVA_HOME,$env:JAVA_HOME,(Join-Path $env:ProgramFiles 'Java/jdk-17'))
    $taskJavaHome=$javaCandidates | Where-Object {$_ -and (Test-Path -LiteralPath (Join-Path $_ 'release')) -and ((Get-Content -LiteralPath (Join-Path $_ 'release') -Raw) -match 'JAVA_VERSION="(17|21|23)(\.|\")')} | Select-Object -First 1
    if(-not $taskJavaHome){throw 'Set ADOFAI_JAVA_HOME to a supported JDK 17 or 21 installation'}
    $env:JAVA_HOME=$taskJavaHome
    $env:ANDROID_HOME=Join-Path $projectRoot 'tools/android-sdk'
    $env:GRADLE_USER_HOME=Join-Path $projectRoot 'tools/android-gradle-cache'
    $env:ADOFAI_BUILD_PYTHON=Join-Path $projectRoot '.venv/Scripts/python.exe'
    if($Task -eq 'assembleRelease'){
        & $env:ADOFAI_BUILD_PYTHON tools/sign_android.py --keytool (Join-Path $taskJavaHome 'bin/keytool.exe')
        if($LASTEXITCODE -ne 0){throw 'Release identity could not be verified; existing keys are preserved'}
    }
    & node tools/npm/package/bin/npm-cli.js --prefix frontend run build
    if($LASTEXITCODE -ne 0){throw 'Frontend build failed'}
    & $env:ADOFAI_BUILD_PYTHON tools/prepare_android.py
    if($LASTEXITCODE -ne 0){throw 'Android resource preparation failed'}
    if($Task -in @('assembleDebugAndroidTest','connectedDebugAndroidTest')){
        & $env:ADOFAI_BUILD_PYTHON tools/prepare_android_tests.py
        if($LASTEXITCODE -ne 0){throw 'Android private test fixture preparation failed'}
    }
    $arguments=@('-p','android','--console=plain','--stacktrace',$Task)
    if($env:HTTPS_PROXY){
        $proxyUri=[uri]$env:HTTPS_PROXY
        $arguments+=@("-Dhttps.proxyHost=$($proxyUri.Host)","-Dhttps.proxyPort=$($proxyUri.Port)","-Dhttp.proxyHost=$($proxyUri.Host)","-Dhttp.proxyPort=$($proxyUri.Port)")
    }
    & ./tools/gradle-8.11.1/bin/gradle.bat @arguments
    if($LASTEXITCODE -ne 0){throw "Android $Task failed"}
} finally {Pop-Location}
