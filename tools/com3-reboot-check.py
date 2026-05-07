#!/usr/bin/env python3
"""Reboot device to fastboot via serial."""
import serial, time, sys

PORT = sys.argv[1] if len(sys.argv) > 1 else "COM3"
s = serial.Serial(PORT, 115200, timeout=0.2)

def read_for(s, sec):
    buf = b''
    end = time.time() + sec
    while time.time() < end:
        chunk = s.read(4096)
        if chunk:
            buf += chunk
    return buf

s.write(b'\n'); read_for(s, 2)
s.write(b'echo ALIVE\n')
if b'ALIVE' not in read_for(s, 3):
    print("Device not responding"); s.close(); sys.exit(1)

# Quick check that symlinks are in place
s.write(b'ls -la /lib/firmware/qca/crbtfw01.tlv /lib/firmware/qca/crnv01.bin\n')
out = read_for(s, 3)
print("Firmware symlinks:", out.decode(errors='replace').strip())

# Reboot to fastboot
print("Rebooting to fastboot...")
s.write(b'/sbin/reboot-bootloader\n')
read_for(s, 5)
s.close()
print("Done.")
