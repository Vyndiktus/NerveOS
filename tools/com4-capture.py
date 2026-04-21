#!/usr/bin/env python3
"""Connect to COM4, capture dmesg dump and run diagnostics."""
import serial, time, sys

PORT = sys.argv[1] if len(sys.argv) > 1 else "COM4"
BAUD = 115200

def read_for(s, seconds):
    buf = b''
    end = time.time() + seconds
    while time.time() < end:
        chunk = s.read(4096)
        if chunk:
            buf += chunk
            sys.stdout.write(chunk.decode(errors='replace'))
            sys.stdout.flush()
    return buf

def cmd(s, c, wait=5):
    s.write(b'\x03')
    time.sleep(0.2)
    s.read(4096)
    s.write(c.encode() + b'\n')
    print(f"\n$ {c}")
    return read_for(s, wait)

s = serial.Serial(PORT, BAUD, timeout=0.1)
print(f"Opened {PORT}. Waiting for boot + dmesg dump (up to 90s)...")

# Read everything for up to 90 seconds (covers 60s UFS wait + dmesg dump)
out = read_for(s, 90)

print("\n\n=== CAPTURE COMPLETE ===")
print(f"Total bytes: {len(out)}")

# Check if we got the dmesg marker
if b'NerveOS initramfs dmesg' in out:
    print("Got dmesg dump!")
elif b'HELLO' in out or b'sh' in out.lower():
    print("Got shell response.")
else:
    print("No dmesg dump yet. Trying to get shell...")

# Try to get a shell and run diagnostics
print("\n=== Trying shell diagnostics ===")
s.write(b'\x03\n')
time.sleep(1)
s.read_all()
s.write(b'echo SHELL_OK\n')
out2 = read_for(s, 3)
if b'SHELL_OK' in out2:
    print("Shell works! Running diagnostics...")
    for c in [
        '/bin/busybox dmesg | /bin/busybox grep -i ufs | /bin/busybox tail -50',
        '/bin/busybox dmesg | /bin/busybox grep -iE "(ufshcd|scsi|disk|sda)" | /bin/busybox tail -30',
        'cat /sys/class/scsi_host/host0/state 2>&1 || echo no_host0',
        'ls /sys/class/scsi_device/ 2>&1',
        'ls /dev/sd* 2>&1 || echo no_sda',
        '/bin/busybox dmesg | /bin/busybox grep -iE "(vreg|regulator|l10a|l9a)" | /bin/busybox tail -20',
    ]:
        cmd(s, c, 6)
else:
    print("Shell not responding.")
    print(f"Last output: {repr(out2)}")

s.close()
