#!/usr/bin/env python3
"""Fix broken shell stdout on COM8 and run diagnostics."""
import serial, time, sys

PORT = "COM8"
BAUD = 115200

s = serial.Serial(PORT, BAUD, timeout=3)
print(f"Opened {PORT}")

def drain(s):
    time.sleep(0.5)
    return s.read_all()

def send_raw(s, data, wait=2.0):
    s.write(data if isinstance(data, bytes) else data.encode())
    time.sleep(wait)
    return s.read_all()

# Break any stuck process
s.write(b'\x03')
drain(s)
s.write(b'\x03')
drain(s)

# Try: exec a fresh shell with fd0 as both in and out
# This re-attaches stdout to ttyGS0
print("Attempting to re-exec shell with stdout on ttyGS0...")
s.write(b'exec /bin/busybox sh <>/dev/ttyGS0 >&0 2>&0\n')
time.sleep(1)
s.read_all()

out = send_raw(s, b'echo FIXED\n', 2)
print(f"After exec re-attach: {repr(out)}")

if b'FIXED' in out:
    print("Shell stdout fixed! Running diagnostics...")
    def cmd(c, wait=3):
        s.write((c + '\n').encode())
        time.sleep(wait)
        out = s.read_all()
        print(f"$ {c}\n{out.decode(errors='replace')}")
        return out

    cmd('echo "=== dmesg UFS ==="')
    cmd('/bin/busybox dmesg | /bin/busybox grep -i ufs | /bin/busybox tail -40', 4)
    cmd('echo "=== dmesg regulators ==="')
    cmd('/bin/busybox dmesg | /bin/busybox grep -iE "(vreg|l10a|l9a|l5a|l3c|regulator)" | /bin/busybox tail -30', 4)
    cmd('echo "=== scsi host state ==="')
    cmd('cat /sys/class/scsi_host/host0/state')
    cmd('ls /sys/class/scsi_device/')
    cmd('ls /dev/sd* 2>&1 || echo "no sda"')
    cmd('echo "=== ufshcd proc ==="')
    cmd('ls /sys/devices/platform/soc@0/1d84000.ufshc/ 2>&1 | head -20')
    cmd('/bin/busybox dmesg | /bin/busybox grep -iE "(ufshcd|scsi|sd [0-9])" | /bin/busybox tail -30', 4)
else:
    print("exec re-attach failed. Trying direct ttyGS0 output...")
    s.write(b'echo DIRECT > /dev/ttyGS0\n')
    time.sleep(1)
    out = s.read_all()
    print(f"Direct ttyGS0 write: {repr(out)}")

    print("\nTrying to open a login on this tty...")
    s.write(b'/sbin/getty -n -l /bin/sh 115200 ttyGS0\n')
    time.sleep(2)
    out = s.read_all()
    print(f"getty result: {repr(out)}")

s.close()
