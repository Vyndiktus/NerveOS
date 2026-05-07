#!/usr/bin/env python3
"""Check all partition names and find BT firmware."""
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

def cmd(s, c, wait=15):
    s.write(c.encode() + b'\n')
    out = read_for(s, wait)
    txt = out.decode(errors='replace').strip()
    lines = txt.split('\n')
    if lines and c[:20] in lines[0]:
        lines = lines[1:]
    print(f"\n$ {c}")
    print('\n'.join(lines) or "(no output)")
    return out

s.write(b'\n'); read_for(s, 2)
s.write(b'echo ALIVE\n')
if b'ALIVE' not in read_for(s, 3):
    print("No response"); s.close(); sys.exit(1)

# Get partition names for all block devices
for dev in ['sdc', 'sdd', 'sdf']:
    cmd(s, f'for d in /sys/block/{dev}/{dev}*/uevent; do n=$(grep PARTNAME $d 2>/dev/null | cut -d= -f2); sz=$(grep PARTSZ $d 2>/dev/null | cut -d= -f2); [ -n "$n" ] && echo "$(basename $(dirname $d)): $n (sz=$sz)"; done', wait=10)

# Try to find modem by looking at sgdisk or fdisk
cmd(s, 'fdisk -l /dev/sda 2>/dev/null | head -50', wait=10)

# Check sgdisk
cmd(s, 'sgdisk -p /dev/sdf 2>/dev/null || gdisk -l /dev/sdf 2>/dev/null || echo "no sgdisk"', wait=10)

# Try mounting sdf partitions to find modem/firmware
cmd(s, '''
mkdir -p /mnt/fw
for d in /dev/sdf1 /dev/sdf2 /dev/sdf3 /dev/sdf4 /dev/sdf5 /dev/sdf6; do
  echo "=== Trying $d ==="
  hexdump -C $d 2>/dev/null | head -3
done
''', wait=20)

# Check if vfat or ext4
cmd(s, '''
for d in /dev/sdf1 /dev/sdf2 /dev/sdf3 /dev/sdf4 /dev/sdf5 /dev/sdf6; do
  t=$(blkid -o value -s TYPE $d 2>/dev/null)
  echo "$d: ${t:-raw}"
done
''', wait=20)

# Try a symlink crbtfw01.tlv → crbtfw21.tlv as a quick test
cmd(s, 'ln -sf /lib/firmware/qca/crbtfw21.tlv /lib/firmware/qca/crbtfw01.tlv && echo "symlink created"', wait=5)
cmd(s, 'ls -la /lib/firmware/qca/crbtfw01.tlv', wait=5)

# Also check if the crnv file is needed
cmd(s, 'ls /lib/firmware/qca/crnv* 2>/dev/null | head -5', wait=5)

s.close()
print("\nDone.")
