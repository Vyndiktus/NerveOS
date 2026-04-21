@echo off
:: HiveOS — Install Android fastboot USB driver (WinUSB for VID_18D1&PID_D00D)
:: Self-elevates if not already admin

net session >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Requesting administrator privileges...
    powershell -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

cd /d "%~dp0"
echo.
echo ============================================================
echo  HiveOS Fastboot USB Driver Installer
echo ============================================================
echo  INF: %~dp0fastboot-driver\android_winusb.inf
echo.

pnputil /add-driver "%~dp0fastboot-driver\android_winusb.inf" /install /force-install
set RESULT=%ERRORLEVEL%

echo.
if %RESULT% EQU 0 (
    echo SUCCESS: Driver added and installed.
    echo Replug the USB cable now.
) else (
    echo RESULT code: %RESULT%
    echo Trying force-update on connected device...
    pnputil /install-inf "%~dp0fastboot-driver\android_winusb.inf"
)

echo.
echo Checking fastboot device visibility:
fastboot devices

echo.
pause
