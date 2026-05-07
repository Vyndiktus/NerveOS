#!/usr/bin/env python3
"""Reboot NerveOS device to fastboot via serial shell."""
import serial, time, sys

PORT = sys.argv[1] if len(sys.argv) > 1 else "COM3"
s = serial.Serial(PORT, 115200, timeout=0.2)
print(f"Opened {PORT}")

def read_for(s, sec):
    buf = b''
    end = time.time() + sec
    while time.time() < end:
        chunk = s.read(4096)
        if chunk:
            buf += chunk
    return buf

# Wake shell
s.write(b'\n')
out = read_for(s, 2)
print(f"Wake: {repr(out[:100])}")

# Run reboot-bootloader
s.write(b'/sbin/reboot-bootloader\n')
out = read_for(s, 5)
print(f"Reboot cmd: {repr(out[:200])}")
s.close()
print("Done — device should be rebooting to fastboot")
