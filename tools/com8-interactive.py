#!/usr/bin/env python3
"""Interactive COM8 debug — long waits, multiple reads, check for any data."""
import serial, time, sys

PORT = sys.argv[1] if len(sys.argv) > 1 else "COM8"
BAUD = 115200

s = serial.Serial(PORT, BAUD, timeout=0.1)
print(f"Opened {PORT} @ {BAUD}")

def read_for(s, seconds):
    """Read everything available over N seconds."""
    buf = b''
    end = time.time() + seconds
    while time.time() < end:
        chunk = s.read(4096)
        if chunk:
            buf += chunk
    return buf

def cmd(s, c, wait=5):
    s.write(b'\x03')  # Ctrl-C
    time.sleep(0.2)
    s.read(4096)
    s.write(c.encode() + b'\n')
    out = read_for(s, wait)
    print(f"$ {c}")
    print(out.decode(errors='replace'))
    return out

# First: just listen for 3 seconds without sending anything
print("=== Listening passively for 3s ===")
out = read_for(s, 3)
print(repr(out))

# Send a newline and listen
print("\n=== Newline + listen 3s ===")
s.write(b'\n')
out = read_for(s, 3)
print(repr(out))

# Ctrl-C and newline
print("\n=== Ctrl-C + newline + listen 3s ===")
s.write(b'\x03\n')
out = read_for(s, 3)
print(repr(out))

# Try stty sane to reset TTY discipline
print("\n=== stty sane ===")
s.write(b'stty sane\n')
out = read_for(s, 3)
print(repr(out))

# Now try commands with long waits
print("\n=== echo test (5s wait) ===")
s.write(b'echo HELLO_WORLD\n')
out = read_for(s, 5)
print(repr(out))

if b'HELLO_WORLD' in out:
    print("GOT OUTPUT!")
    # Run diagnostics
    for c in [
        '/bin/busybox dmesg | /bin/busybox grep -i ufs | /bin/busybox tail -30',
        'cat /sys/class/scsi_host/host0/state',
        'ls /dev/sd* 2>&1 || echo no_sda',
        '/bin/busybox dmesg | /bin/busybox grep -iE "(vreg|regulator|clk)" | /bin/busybox tail -20',
    ]:
        cmd(s, c, 6)
else:
    # Try exec to reset fds
    print("No output. Trying exec to reset fds...")
    s.write(b'exec /bin/busybox sh\n')
    out = read_for(s, 3)
    print(f"exec sh: {repr(out)}")

    s.write(b'echo AFTER_EXEC\n')
    out = read_for(s, 5)
    print(f"after exec: {repr(out)}")

s.close()
