#!/usr/bin/env python3
"""Probe COM8 shell state and re-establish if needed."""
import serial, time, sys

PORT = "COM8"
BAUD = 115200

def send(s, cmd, wait=2.0):
    s.write(b'\n')
    time.sleep(0.3)
    s.read_all()
    s.write(cmd.encode() + b'\n')
    time.sleep(wait)
    out = s.read_all()
    print(f">>> {cmd}")
    print(repr(out))
    return out

try:
    s = serial.Serial(PORT, BAUD, timeout=2)
    print(f"Opened {PORT}")
except Exception as e:
    print(f"Cannot open {PORT}: {e}")
    sys.exit(1)

# Send Ctrl-C to break any stuck process
s.write(b'\x03\n')
time.sleep(1)
s.read_all()

# Try a simple echo
out = send(s, 'echo ALIVE', 2)
if b'ALIVE' in out:
    print("Shell responsive!")
else:
    print("Shell not echoing output — trying /bin/busybox sh")
    s.write(b'/bin/busybox sh\n')
    time.sleep(1)
    s.read_all()
    out = send(s, 'echo ALIVE2', 2)
    if b'ALIVE2' in out:
        print("busybox sh works!")
    else:
        print("Still not responding. Sending Ctrl-D then newline.")
        s.write(b'\x04\n')
        time.sleep(1)
        s.read_all()
        out = send(s, 'echo ALIVE3', 2)
        print("After Ctrl-D:", repr(out))

# Check UFS dmesg
print("\n--- UFS dmesg ---")
out = send(s, '/bin/busybox dmesg 2>&1 | /bin/busybox grep -i ufs | /bin/busybox tail -30', 4)

# Check SCSI
print("\n--- SCSI state ---")
out = send(s, 'cat /sys/class/scsi_host/host0/state 2>&1', 2)

# List scsi_device
print("\n--- /sys/class/scsi_device ---")
out = send(s, 'ls /sys/class/scsi_device/ 2>&1', 2)

# Check /dev
print("\n--- /dev block devices ---")
out = send(s, 'ls /dev/sd* /dev/disk* 2>&1', 2)

# Check regulator dependency
print("\n--- regulator/clock errors ---")
out = send(s, '/bin/busybox dmesg 2>&1 | /bin/busybox grep -E "(ufs|regulator|vreg|l10a|l9a|l5a|l3c|s4a)" | /bin/busybox tail -40', 4)

s.close()
