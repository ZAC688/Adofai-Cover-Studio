param([ValidateSet('assembleDebug','assembleRelease','connectedDebugAndroidTest','testDebugUnitTest','lintDebug')][string]$Task='assembleDebug')
$ErrorActionPreference='Stop'
$projectRoot=Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot
try {
    $env:JAVA_HOME=if($env:ADOFAI_JAVA_HOME){$env:ADOFAI_JAVA_HOME}else{'C:\Program Files\Java\jdk-17'}
    $env:ANDROID_HOME=Join-Path $projectRoot 'tools/android-sdk'
    $env:GRADLE_USER_HOME=Join-Path $projectRoot 'tools/android-gradle-cache'
    $env:ADOFAI_BUILD_PYTHON=Join-Path $projectRoot '.venv/Scripts/python.exe'
    & node tools/npm/package/bin/npm-cli.js --prefix frontend run build
    if($LASTEXITCODE -ne 0){throw 'Frontend build failed'}
    & $env:ADOFAI_BUILD_PYTHON tools/prepare_android.py
    if($LASTEXITCODE -ne 0){throw 'Android resource preparation failed'}
    $arguments=@('-p','android','--console=plain','--stacktrace',$Task)
    if($env:HTTPS_PROXY){
        $proxyUri=[uri]$env:HTTPS_PROXY
        $arguments+=@("-Dhttps.proxyHost=$($proxyUri.Host)","-Dhttps.proxyPort=$($proxyUri.Port)","-Dhttp.proxyHost=$($proxyUri.Host)","-Dhttp.proxyPort=$($proxyUri.Port)")
    }
    & ./tools/gradle-8.11.1/bin/gradle.bat @arguments
    if($LASTEXITCODE -ne 0){throw "Android $Task failed"}
} finally {Pop-Location}
