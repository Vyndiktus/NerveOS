#!/usr/bin/env python3
"""Transfer patched btqca.ko to device via serial and install it."""
import serial, time, sys, subprocess, base64, gzip, os

PORT = sys.argv[1] if len(sys.argv) > 1 else "COM3"

# Get the module from WSL
result = subprocess.run(
    ["wsl", "-d", "Debian", "-u", "root", "--",
     "bash", "-c", "cat /opt/NerveOS/build/cepheus/build/linux-4a8d88483/drivers/bluetooth/btqca.ko"],
    capture_output=True
)
if result.returncode != 0:
    print("Failed to read btqca.ko from WSL:", result.stderr)
    sys.exit(1)

ko_data = result.stdout
print(f"btqca.ko: {len(ko_data)} bytes")

# Compress
ko_gz = gzip.compress(ko_data, compresslevel=9)
print(f"Compressed: {len(ko_gz)} bytes")

# Base64
ko_b64 = base64.b64encode(ko_gz).decode()
print(f"Base64: {len(ko_b64)} chars")

# Open serial
s = serial.Serial(PORT, 115200, timeout=0.3)

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

# Wake
s.write(b'\n'); read_for(s, 2)
s.write(b'echo ALIVE\n')
if b'ALIVE' not in read_for(s, 3):
    print("Not responding"); s.close(); sys.exit(1)

# Find module path
cmd(s, 'find /lib/modules -name "btqca.ko" 2>/dev/null | head -3', wait=10)

# Clear temp file
cmd(s, 'rm -f /tmp/btqca_b64; echo cleared', wait=5)

# Send in chunks
CHUNK = 300
chunks = [ko_b64[i:i+CHUNK] for i in range(0, len(ko_b64), CHUNK)]
print(f"\nSending {len(chunks)} chunks...")

for i, chunk in enumerate(chunks):
    s.write(f'printf "%s" "{chunk}" >> /tmp/btqca_b64\n'.encode())
    read_for(s, 0.3)
    if i % 50 == 0:
        print(f"  chunk {i}/{len(chunks)}")

# Verify
s.write(b'wc -c /tmp/btqca_b64\n')
out = read_for(s, 5)
print(f"Verify: {out.decode(errors='replace').strip()}")

# Find module dir
s.write(b'KV=$(uname -r); echo $KV\n')
out = read_for(s, 3)
kver = out.decode(errors='replace').strip().split('\n')[-1].strip()
print(f"Kernel version: {kver}")

moddir = f"/lib/modules/{kver}/kernel/drivers/bluetooth"
cmd(s, f'ls {moddir}/btqca.ko', wait=5)

# Decode and install
print("\nDecoding and installing...")
cmd(s, f'base64 -d /tmp/btqca_b64 | gunzip > {moddir}/btqca.ko && echo "installed"', wait=15)
cmd(s, f'ls -lh {moddir}/btqca.ko', wait=5)

# Rebuild module deps
cmd(s, 'depmod -a 2>&1 | head -5 || echo "depmod done"', wait=15)

print("\nModule installed. Reload BT...")
cmd(s, 'rmmod hci_uart btqca 2>&1; sleep 2; modprobe hci_uart 2>&1 && echo "reloaded"', wait=20)

# Wait for BT init
print("Waiting 15s for BT init...")
s.write(b'sleep 15\n'); read_for(s, 17)

cmd(s, 'dmesg | grep -iE "(bluetooth|hci|qca|wcn|crbt|crnv)" | tail -20', wait=8)

s.close()
print("\nDone.")
