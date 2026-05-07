#!/usr/bin/env python3
"""Install patched btqca.ko with explicit path and reboot to test."""
import serial, time, sys, subprocess, base64, gzip

PORT = sys.argv[1] if len(sys.argv) > 1 else "COM3"
MODPATH = "/lib/modules/6.11.0-sm8150/kernel/drivers/bluetooth/btqca.ko"

# Get module from WSL
result = subprocess.run(
    ["wsl", "-d", "Debian", "-u", "root", "--",
     "bash", "-c", "cat /opt/NerveOS/build/cepheus/build/linux-4a8d88483/drivers/bluetooth/btqca.ko"],
    capture_output=True
)
ko_data = result.stdout
print(f"btqca.ko: {len(ko_data)} bytes")
ko_gz = gzip.compress(ko_data, compresslevel=9)
ko_b64 = base64.b64encode(ko_gz).decode()
print(f"Compressed+b64: {len(ko_b64)} chars in {(len(ko_b64)+299)//300} chunks")

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

s.write(b'\n'); read_for(s, 2)
s.write(b'echo ALIVE\n')
if b'ALIVE' not in read_for(s, 3):
    print("Not responding"); s.close(); sys.exit(1)

# Verify existing module path
cmd(s, f'ls -lh {MODPATH}', wait=5)

# Transfer
s.write(b'rm -f /tmp/btqca_b64\n'); read_for(s, 2)
CHUNK = 300
chunks = [ko_b64[i:i+CHUNK] for i in range(0, len(ko_b64), CHUNK)]
print(f"Sending {len(chunks)} chunks...")
for i, chunk in enumerate(chunks):
    s.write(f'printf "%s" "{chunk}" >> /tmp/btqca_b64\n'.encode())
    read_for(s, 0.3)
    if i % 20 == 0:
        print(f"  {i}/{len(chunks)}")

# Verify transfer
s.write(b'wc -c /tmp/btqca_b64\n')
out = read_for(s, 5)
print(f"Transfer verify: {out.decode(errors='replace').strip()}")

# Decode and install
cmd(s, f'base64 -d /tmp/btqca_b64 | gunzip > {MODPATH} && ls -lh {MODPATH}', wait=20)

# Reboot to fastboot for clean test
print("\nRebooting to fastboot for clean BT test...")
s.write(b'/sbin/reboot-bootloader\n')
read_for(s, 5)
s.close()
print("Done — device rebooting.")
