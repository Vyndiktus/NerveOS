#!/usr/bin/env python3
"""Create BT firmware symlinks and reload HCI UART to test BT init."""
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

# Verify symlinks
cmd(s, 'ls -la /lib/firmware/qca/crbtfw01.tlv', wait=5)

# Create NVM symlink (crnv01.bin → crnv21.bin)
cmd(s, 'ln -sf /lib/firmware/qca/crnv21.bin /lib/firmware/qca/crnv01.bin && ls -la /lib/firmware/qca/crnv01.bin', wait=5)

# Unload BT modules
print("\n=== Unloading BT modules ===")
cmd(s, 'rmmod hci_uart btqca 2>&1 || echo "rmmod done"', wait=15)
cmd(s, 'lsmod | grep -E "(hci|bt)" | head -5', wait=5)

# Wait a moment
s.write(b'sleep 2\n'); read_for(s, 4)

# Reload modules
print("\n=== Reloading HCI UART ===")
cmd(s, 'modprobe hci_uart 2>&1 && echo "modprobe ok"', wait=15)
cmd(s, 'dmesg | tail -20', wait=8)

# Wait for BT init (it takes up to 10s)
print("\nWaiting for BT init...")
s.write(b'sleep 15\n'); read_for(s, 17)

# Check BT status
cmd(s, 'dmesg | grep -iE "(bluetooth|hci|qca|wcn|crbt|crnv)" | tail -30', wait=8)
cmd(s, 'ls /sys/class/bluetooth/ 2>/dev/null || echo "no BT devices"', wait=5)
cmd(s, 'hciconfig hci0 2>/dev/null | head -10 || cat /sys/class/bluetooth/hci0/type 2>/dev/null || echo "no hci0"', wait=5)

# If BT is up, scan
cmd(s, 'hciconfig hci0 up 2>/dev/null && hcitool scan --length=5 2>/dev/null | head -10 || echo "BT scan not available"', wait=20)

s.close()
print("\nDone.")
