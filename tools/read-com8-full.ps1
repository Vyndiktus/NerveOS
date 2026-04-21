$port = New-Object System.IO.Ports.SerialPort("COM8", 115200, [System.IO.Ports.Parity]::None, 8, [System.IO.Ports.StopBits]::One)
$port.ReadTimeout = 15000
$port.Open()
Start-Sleep -Milliseconds 500
$port.WriteLine('dmesg | grep -i "ufs\|ufshcd\|uecpa\|scsi\|sda\|qmp_ufs\|phy\|PRE-LINK\|POST-LINK\|link_start\|Direct-Access\|sd 0\|clk\|regulator\|rpm\|phy init\|timed\|error\|panic\|oops" | head -200 ; echo FULL_DONE')
Start-Sleep -Milliseconds 12000
$data = $port.ReadExisting()
$port.Close()
Write-Output $data
