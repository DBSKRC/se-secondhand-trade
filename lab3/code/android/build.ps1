param(
    [string]$SdkRoot = $env:ANDROID_HOME,
    [string]$JdkRoot = $env:JAVA_HOME
)
$ErrorActionPreference = 'Stop'
$project = $PSScriptRoot
$build = Join-Path (Split-Path $project -Parent) 'build/apk'
if (!$SdkRoot) {
    $SdkRoot = Join-Path (Split-Path $project -Parent) 'build/android-sdk'
}
$SdkRoot = (Resolve-Path -LiteralPath $SdkRoot).Path
if (!$JdkRoot) {
    $compiler = Get-Command javac.exe -ErrorAction Stop
    $target = (Get-Item -LiteralPath $compiler.Source).ResolvedTarget
    if (!$target) { $target = $compiler.Source }
    $JdkRoot = Split-Path (Split-Path $target -Parent) -Parent
}
$jdkBin = Join-Path $JdkRoot 'bin'
$tools = Join-Path $SdkRoot 'build-tools/35.0.0'
$platform = Join-Path $SdkRoot 'platforms/android-35/android.jar'
if (!(Test-Path -LiteralPath $platform) -or !(Test-Path -LiteralPath $tools)) {
    throw 'Install Android platform 35 and build-tools 35.0.0.'
}
New-Item -ItemType Directory -Force -Path $build | Out-Null

function Invoke-Step($Executable, [string[]]$Arguments) {
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Executable failed (exit $LASTEXITCODE)"
    }
}

$classes = Join-Path $build 'classes'
New-Item -ItemType Directory -Force -Path $classes | Out-Null
$java = Join-Path $project 'src/edu/campus/marketplace/MainActivity.java'
$compiled = Join-Path $build 'resources.zip'
$unsigned = Join-Path $build 'resources.apk'
$dex = Join-Path $build 'code.zip'
$combined = Join-Path $build 'unsigned.apk'
$aligned = Join-Path $build 'aligned.apk'
$keystore = Join-Path $build 'debug.keystore'
$signed = Join-Path $build 'campus-market-debug.apk'

Invoke-Step (Join-Path $tools 'aapt2.exe') @(
    'compile', '--dir', (Join-Path $project 'res'), '-o', $compiled
)
Invoke-Step (Join-Path $tools 'aapt2.exe') @(
    'link', '-I', $platform, '--manifest',
    (Join-Path $project 'AndroidManifest.xml'), '-o', $unsigned, $compiled
)
Invoke-Step (Join-Path $jdkBin 'javac.exe') @(
    '--release', '8', '-encoding', 'UTF-8', '-classpath', $platform, '-d', $classes, $java
)
$classFiles = @(Get-ChildItem -LiteralPath $classes -Recurse -Filter '*.class' |
    Select-Object -ExpandProperty FullName)
# Call the SDK jars directly because cmd.exe can misread non-ASCII workspace paths.
Invoke-Step (Join-Path $jdkBin 'java.exe') (@(
    '-cp', (Join-Path $tools 'lib/d8.jar'), 'com.android.tools.r8.D8',
    '--lib', $platform, '--min-api', '26', '--output', $dex
) + $classFiles)
$merge = @'
import pathlib
import sys
import zipfile
apk, dex, output = map(pathlib.Path, sys.argv[1:])
with zipfile.ZipFile(apk) as resources, zipfile.ZipFile(dex) as bytecode:
    with zipfile.ZipFile(output, "w") as result:
        for info in resources.infolist():
            result.writestr(info, resources.read(info))
        for info in bytecode.infolist():
            result.writestr(info, bytecode.read(info))
'@
$merge | python - $unsigned $dex $combined
if ($LASTEXITCODE -ne 0) { throw 'Could not assemble Android archive.' }
Invoke-Step (Join-Path $tools 'zipalign.exe') @('-f', '4', $combined, $aligned)
if (!(Test-Path -LiteralPath $keystore)) {
    Invoke-Step (Join-Path $jdkBin 'keytool.exe') @(
        '-genkeypair', '-keystore', $keystore,
        '-storepass', 'android', '-keypass', 'android',
        '-alias', 'androiddebugkey', '-keyalg', 'RSA', '-keysize', '2048',
        '-validity', '10000', '-dname', 'CN=Android Debug,O=Campus'
    )
}
$signer = Join-Path $tools 'lib/apksigner.jar'
Invoke-Step (Join-Path $jdkBin 'java.exe') @(
    '-jar', $signer, 'sign', '--ks', $keystore, '--ks-pass', 'pass:android',
    '--key-pass', 'pass:android', '--out', $signed, $aligned
)
Invoke-Step (Join-Path $jdkBin 'java.exe') @(
    '-jar', $signer, 'verify', '--verbose', $signed
)
Write-Output $signed
