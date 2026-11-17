param(
    [string]$Serial,
    [string]$Apk = (Join-Path $PSScriptRoot '../build/apk/campus-market-debug.apk')
)
$ErrorActionPreference = 'Stop'
$localAdb = Join-Path $PSScriptRoot '../build/android-sdk/platform-tools/adb.exe'
if (Test-Path -LiteralPath $localAdb) {
    $adb = (Resolve-Path -LiteralPath $localAdb).Path
} elseif ($env:ANDROID_HOME -and (Test-Path (Join-Path $env:ANDROID_HOME 'platform-tools/adb.exe'))) {
    $adb = Join-Path $env:ANDROID_HOME 'platform-tools/adb.exe'
} else {
    $adb = (Get-Command adb.exe -ErrorAction Stop).Source
}
$apkPath = (Resolve-Path -LiteralPath $Apk).Path
$device = @()
if ($Serial) { $device = @('-s', $Serial) }
& $adb @device install -r $apkPath
if ($LASTEXITCODE) { throw 'APK installation failed. Check the device and USB debugging.' }
& $adb @device reverse tcp:8871 tcp:8871
if ($LASTEXITCODE) { throw 'Local port forwarding failed.' }
& $adb @device shell am start -n edu.campus.marketplace/.MainActivity
if ($LASTEXITCODE) { throw 'Could not start Campus Marketplace.' }
