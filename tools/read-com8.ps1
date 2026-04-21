$port = New-Object System.IO.Ports.SerialPort("COM8", 115200, [System.IO.Ports.Parity]::None, 8, [System.IO.Ports.StopBits]::One)
$port.ReadTimeout = 8000
$port.Open()
Start-Sleep -Milliseconds 500
$port.WriteLine('grep -i "ufshcd\|UECPA\|scsi host\|Direct-Access\|sda\|link_startup" /sys/kernel/debug/dynamic_debug/control 2>/dev/null; cat /proc/partitions 2>/dev/null; ls /dev/sd* /dev/block/ 2>/dev/null; echo END')
Start-Sleep -Milliseconds 5000
$data = $port.ReadExisting()
$port.Close()
Write-Output $data
