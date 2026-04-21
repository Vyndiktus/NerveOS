#!/usr/bin/env python3
"""Read UFS host controller registers directly via /dev/mem."""
import serial, time, sys

s = serial.Serial('COM8', 115200, timeout=0.1)

def read_for(s, seconds):
    buf = b''
    end = time.time() + seconds
    while time.time() < end:
        c = s.read(4096); buf += c
    return buf

def cmd(s, c, wait=4):
    s.write(b'\x03'); time.sleep(0.15); s.read(4096)
    s.write(c.encode() + b'\n')
    out = read_for(s, wait).decode(errors='replace')
    print(f"$ {c}\n{out}")
    return out

# Re-attach stdout
s.write(b'exec /bin/busybox sh <>/dev/ttyGS0 >&0 2>&0\n')
time.sleep(0.5); s.read_all()
if 'ALIVE' not in cmd(s, 'echo ALIVE', 2):
    print("Shell not responding"); s.close(); sys.exit(1)

# UFS HC base = 0x1d84000
# Key registers (UFSHCI 3.0 spec offsets):
# 0x00 = CAPS, 0x08 = VER, 0x34 = HCE (or 0x38), 0x40 = IS, 0x44 = IE
# 0x48 = HCS, 0x58 = UTRIACR
# Qualcomm-specific: 0x200 = UFS_SYS1CLK_1US

cmd(s, 'echo "=== UFS HC registers ==="')
for off, name in [
    (0x00, 'CAPS'),
    (0x08, 'VER'),
    (0x30, 'UTRLDBR'),
    (0x34, 'HCE?0x34'),
    (0x38, 'UTMRLRSR/HCE?0x38'),
    (0x40, 'IS'),
    (0x44, 'IE'),
    (0x48, 'HCS'),
    (0x50, 'UECPA'),
    (0x54, 'UECDL'),
    (0x58, 'UECN'),
    (0x5C, 'UECT'),
    (0x60, 'UECDME'),
    (0x64, 'UTRIACR'),
    (0x200, 'UFS_SYS1CLK_1US'),
]:
    addr = 0x1d84000 + off
    cmd(s, f'/bin/busybox devmem 0x{addr:08x} 32 2>&1 || echo fail', 3)

# Also check REG_CONTROLLER_ENABLE specifically
# Different versions use 0x34 or 0x38
cmd(s, 'echo "=== QMP UFS PHY registers ==="')
for off, name in [
    (0x00, 'PHY_START'),
    (0x08, 'PHY_STATUS'),
    (0x1C, 'PHY_PCS_READY_STATUS'),
]:
    addr = 0x1d87000 + off
    cmd(s, f'/bin/busybox devmem 0x{addr:08x} 32 2>&1 || echo fail', 3)

s.close()
