#!/usr/bin/env python3
"""Read full dmesg from device and print UFS-related lines."""
import serial, time, sys

s = serial.Serial('COM8', 115200, timeout=0.1)

def read_for(s, seconds):
    buf = b''
    end = time.time() + seconds
    while time.time() < end:
        c = s.read(4096)
        if c: buf += c
    return buf

def cmd(s, c, wait=8):
    s.write(b'\x03'); time.sleep(0.2); s.read(4096)
    s.write(c.encode() + b'\n')
    out = read_for(s, wait)
    return out.decode(errors='replace')

s.write(b'exec /bin/busybox sh <>/dev/ttyGS0 >&0 2>&0\n')
time.sleep(0.5); s.read_all()
r = cmd(s, 'echo OK', 2)
if 'OK' not in r:
    print("Shell not responding"); s.close(); sys.exit(1)

# Get full dmesg
print("=== FULL DMESG ===")
out = cmd(s, '/bin/busybox dmesg 2>&1', 15)
for line in out.splitlines():
    print(line)

s.close()
