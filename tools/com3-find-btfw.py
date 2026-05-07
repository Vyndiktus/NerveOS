#!/usr/bin/env python3
"""Find BT firmware in MIUI partitions and extract crbtfw01.tlv."""
import serial, time, sys, base64

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

def cmd(s, c, wait=10):
    s.write(c.encode() + b'\n')
    out = read_for(s, wait)
    txt = out.decode(errors='replace').strip()
    lines = txt.split('\n')
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

# List all partitions
cmd(s, 'ls /dev/sda* | head -40', wait=5)

# Check partition labels via blkid
cmd(s, 'blkid /dev/sda* 2>/dev/null | head -40', wait=15)

# Try to read partition names from GPT
cmd(s, 'cat /proc/partitions | head -40', wait=5)

# Check for modem/vendor partitions by trying to mount them
# The modem partition on Mi 9 is usually one of the early partitions
# Vendor would be a larger ext4 partition
cmd(s, 'for d in /dev/sda{1..30}; do t=$(blkid -o value -s TYPE $d 2>/dev/null); [ -n "$t" ] && echo "$d: $t"; done', wait=30)

# Try to mount and search key partitions
cmd(s, 'mkdir -p /mnt/modem /mnt/vendor 2>/dev/null; echo ok', wait=3)

# Look for the vendor partition (ext2/ext4, likely sda21 or so)
cmd(s, 'for d in /dev/sda{15..30}; do sz=$(blockdev --getsz $d 2>/dev/null); [ "$sz" -gt "200000" ] 2>/dev/null && echo "$d size=$sz" && mount -r $d /mnt/vendor 2>/dev/null && ls /mnt/vendor/firmware/qca/ 2>/dev/null | grep -i "crbt\|wcn" | head -5 && umount /mnt/vendor 2>/dev/null; done', wait=60)

# Check if partition names are available via sysfs
cmd(s, 'ls /sys/class/block/ | grep sda | head -40', wait=5)
cmd(s, 'for d in /sys/block/sda/sda*/uevent; do n=$(grep PARTNAME $d 2>/dev/null | cut -d= -f2); [ -n "$n" ] && echo "$(basename $(dirname $d)): $n"; done', wait=10)

s.close()
print("\nDone.")
