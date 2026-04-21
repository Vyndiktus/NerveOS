foreach ($p in @('COM1','COM3','COM4','COM5','COM6','COM7','COM8','COM9')) {
    try {
        $port = New-Object System.IO.Ports.SerialPort($p, 115200, [System.IO.Ports.Parity]::None, 8, [System.IO.Ports.StopBits]::One)
        $port.ReadTimeout = 1500
        $port.Open()
        Start-Sleep -Milliseconds 300
        $port.WriteLine('')
        Start-Sleep -Milliseconds 800
        $data = $port.ReadExisting()
        $port.Close()
        if ($data.Length -gt 0) {
            Write-Host ("=== " + $p + " has data ===")
            Write-Host $data
        } else {
            Write-Host ($p + ": open OK, no data")
        }
    } catch {
        Write-Host ($p + ": " + $_.Exception.Message.Split('.')[0])
    }
}
