$port = New-Object System.IO.Ports.SerialPort("COM8", 115200, [System.IO.Ports.Parity]::None, 8, [System.IO.Ports.StopBits]::One)
$port.ReadTimeout = 12000
$port.Open()
Start-Sleep -Milliseconds 500
$port.WriteLine('cat /dev/kmsg 2>/dev/null | grep -i "ufs\|ufshcd\|uecpa\|scsi\|sda\|qmp_ufs\|phy\|PRE-LINK\|T_TxAct\|link_start\|Direct-Access\|sd 0" ; echo KMSG_DONE')
Start-Sleep -Milliseconds 10000
$data = $port.ReadExisting()
$port.Close()
Write-Output $data
