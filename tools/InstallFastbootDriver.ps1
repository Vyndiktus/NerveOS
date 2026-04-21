#Requires -RunAsAdministrator
$inf = "$PSScriptRoot\fastboot-driver\android_winusb.inf"
Write-Host "Installing: $inf" -ForegroundColor Cyan

$result = pnputil /add-driver $inf /install /force-install 2>&1
$result | ForEach-Object { Write-Host $_ }

if ($LASTEXITCODE -eq 0) {
    Write-Host "`nSUCCESS - driver installed." -ForegroundColor Green
    Write-Host "Replug the USB cable now." -ForegroundColor Yellow
} else {
    Write-Host "`nFAILED (exit $LASTEXITCODE)" -ForegroundColor Red
}

Write-Host "`nfastboot devices output:"
& fastboot devices

Read-Host "`nPress Enter to close"
