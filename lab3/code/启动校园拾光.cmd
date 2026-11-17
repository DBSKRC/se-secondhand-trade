@echo off
cd /d "%~dp0"
if exist "build\android-sdk\platform-tools\adb.exe" (
  "build\android-sdk\platform-tools\adb.exe" reverse tcp:8871 tcp:8871
)
python -m tools.seed_demo
if errorlevel 1 goto failed
python -m campus.mobile --db data/visual-demo.db --open
if errorlevel 1 goto failed
exit /b 0
:failed
pause
exit /b 1
