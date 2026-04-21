#!/usr/bin/env python3
"""Unbind/rebind ufshcd-qcom driver and check UFS state."""
import serial, time, sys

s = serial.Serial('COM8', 115200, timeout=0.1)

def read_for(s, seconds):
    buf = b''
    end = time.time() + seconds
    while time.time() < end:
        c = s.read(4096)
        if c: buf += c
    return buf

def cmd(s, c, wait=5):
    s.write(b'\x03')
    time.sleep(0.2)
    s.read(4096)
    s.write(c.encode() + b'\n')
    out = read_for(s, wait)
    text = out.decode(errors='replace')
    print(f"$ {c}")
    print(text)
    return text

# Re-attach stdout
s.write(b'exec /bin/busybox sh <>/dev/ttyGS0 >&0 2>&0\n')
time.sleep(0.5); s.read_all()
out = cmd(s, 'echo OK', 2)
if 'OK' not in out:
    print("Shell not responding"); s.close(); sys.exit(1)

# Check current UFS state
cmd(s, 'cat /sys/class/scsi_host/host0/state', 3)
cmd(s, 'ls /sys/devices/platform/soc@0/1d84000.ufshc/host0/ 2>&1 | head', 3)

# Unbind ufshcd driver
print("=== Unbinding ufshcd-qcom ===")
out = cmd(s, 'echo 1d84000.ufshc > /sys/bus/platform/drivers/ufshcd-qcom/unbind 2>&1; echo unbind_done', 5)

# Wait a moment
time.sleep(2)

# Rebind ufshcd driver
print("=== Rebinding ufshcd-qcom ===")
out = cmd(s, 'echo 1d84000.ufshc > /sys/bus/platform/drivers/ufshcd-qcom/bind 2>&1; echo bind_done', 5)

# Wait for async scan
print("=== Waiting for async scan (10s) ===")
time.sleep(10)

# Check dmesg for UFS messages
cmd(s, '/bin/busybox dmesg | /bin/busybox tail -30', 5)

# Check state
cmd(s, 'ls /dev/sd* 2>&1 || echo no_sda', 3)
cmd(s, 'ls /sys/class/scsi_device/ 2>&1', 3)
cmd(s, 'cat /sys/class/scsi_host/host0/state 2>&1 || echo no_host', 3)

# Check UFS sysfs
cmd(s, 'ls /sys/devices/platform/soc@0/1d84000.ufshc/host0/ 2>&1 | head -20', 3)

# Try manual scan
cmd(s, 'echo "- - -" > /sys/class/scsi_host/host0/scan 2>&1 || echo scan_fail', 3)
cmd(s, 'ls /dev/sd* 2>&1 || echo no_sda', 3)

s.close()
