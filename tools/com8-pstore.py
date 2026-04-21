#!/usr/bin/env python3
"""Connect to COM8, fix shell, read pstore crash dump and UFS state."""
import serial, time, sys

s = serial.Serial('COM8', 115200, timeout=0.1)
print(f"Opened COM8")

def read_for(s, seconds):
    buf = b''
    end = time.time() + seconds
    while time.time() < end:
        chunk = s.read(4096)
        if chunk:
            buf += chunk
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

# Re-attach stdout to ttyGS0
s.write(b'exec /bin/busybox sh <>/dev/ttyGS0 >&0 2>&0\n')
time.sleep(0.5)
s.read_all()

out = cmd(s, 'echo SHELL_OK', 3)
if 'SHELL_OK' not in out:
    print("Shell not responding, trying Ctrl-C...")
    s.write(b'\x03\n')
    time.sleep(1)
    s.read_all()
    out = cmd(s, 'echo SHELL_OK', 3)
    if 'SHELL_OK' not in out:
        print("Shell not responding at all")
        s.close()
        sys.exit(1)

print("=== Shell working! ===")

# Mount pstore
cmd(s, 'mkdir -p /sys/fs/pstore && mount -t pstore none /sys/fs/pstore 2>&1 || echo already_mounted', 3)
cmd(s, 'ls /sys/fs/pstore/ 2>&1', 3)

# Read previous crash
out = cmd(s, 'ls /sys/fs/pstore/*.txt /sys/fs/pstore/console-ramoops* /sys/fs/pstore/dmesg-ramoops* 2>&1', 3)
for fname in ['console-ramoops-0', 'dmesg-ramoops-0', 'console-ramoops']:
    cmd(s, f'cat /sys/fs/pstore/{fname} 2>/dev/null | head -100', 8)

# UFS state
cmd(s, 'cat /sys/class/scsi_host/host0/state 2>&1', 3)
cmd(s, 'ls /sys/devices/platform/soc@0/1d84000.ufshc/ 2>&1 | head -20', 3)

# Trigger UFS rescan manually
print("=== Triggering SCSI host scan ===")
cmd(s, 'echo "- - -" > /sys/class/scsi_host/host0/scan 2>&1 || echo fail', 3)
cmd(s, 'ls /dev/sd* 2>&1 || echo no_sda', 3)
cmd(s, 'ls /sys/class/scsi_device/ 2>&1', 3)

s.close()
