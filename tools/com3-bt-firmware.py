#!/usr/bin/env python3
"""Check BT firmware and install crbtfw01.tlv if available."""
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

def cmd(s, c, wait=8):
    s.write(c.encode() + b'\n')
    out = read_for(s, wait)
    txt = out.decode(errors='replace').strip()
    lines = txt.split('\n')
    # strip echo line
    if lines and c[:20] in lines[0]:
        lines = lines[1:]
    print(f"\n$ {c}")
    print('\n'.join(lines) or "(no output)")
    return out

s.write(b'\n')
read_for(s, 2)
s.write(b'echo ALIVE\n')
if b'ALIVE' not in read_for(s, 3):
    print("No response"); s.close(); sys.exit(1)

# Check if firmware already exists
cmd(s, 'ls /lib/firmware/qca/ 2>/dev/null || echo "no qca dir"')
cmd(s, 'ls -la /lib/firmware/qca/crbt* 2>/dev/null || echo "not found"')
cmd(s, 'find /lib/firmware -name "crbt*" 2>/dev/null || echo "not found"')

# Check sda31 rootfs for firmware
cmd(s, 'ls /dev/sda31 2>/dev/null || echo "no sda31"')
cmd(s, 'mount | grep sda', wait=3)

# Check current rootfs firmware
cmd(s, 'ls /lib/firmware/qca/ 2>/dev/null | head -20')
cmd(s, 'ls /lib/firmware/ | head -20')

# Check if we can mount sda31 to get there
cmd(s, 'mkdir -p /mnt/sda31 && mount /dev/sda31 /mnt/sda31 2>&1 && ls /mnt/sda31/lib/firmware/qca/ 2>/dev/null | head -10', wait=10)
cmd(s, 'ls -la /mnt/sda31/lib/firmware/qca/crbt* 2>/dev/null || echo "crbtfw not on sda31"')

# Check for the firmware in the current running rootfs
cmd(s, 'find / -name "crbtfw01.tlv" 2>/dev/null | head -5')

s.close()
print("\nDone.")
