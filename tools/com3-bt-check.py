#!/usr/bin/env python3
"""Check BT and WiFi status on COM3 after RF_CLK2 fix."""
import serial, time, sys

PORT = sys.argv[1] if len(sys.argv) > 1 else "COM3"
BAUD = 115200

s = serial.Serial(PORT, BAUD, timeout=0.2)
print(f"Opened {PORT} @ {BAUD}")

def read_for(s, seconds):
    buf = b''
    end = time.time() + seconds
    while time.time() < end:
        chunk = s.read(4096)
        if chunk:
            buf += chunk
    return buf

def cmd(s, c, wait=8):
    s.write(c.encode() + b'\n')
    out = read_for(s, wait)
    print(f"\n$ {c}")
    print(out.decode(errors='replace').strip())
    return out

# Wake the terminal
print("=== Waking terminal ===")
s.write(b'\n')
out = read_for(s, 3)
print(repr(out[:200]))

# If login prompt, try root with no password
if b'login:' in out or b'Login:' in out:
    print("=== Logging in as root ===")
    s.write(b'root\n')
    out = read_for(s, 3)
    print(repr(out[:200]))
    if b'Password' in out or b'password' in out:
        s.write(b'\n')  # blank password
        out = read_for(s, 3)
        print(repr(out[:200]))

# Try a command
s.write(b'echo ALIVE\n')
out = read_for(s, 4)
print(f"echo test: {repr(out[:200])}")

if b'ALIVE' not in out:
    print("No response — trying Ctrl-C then newline")
    s.write(b'\x03\n')
    out = read_for(s, 3)
    print(repr(out[:200]))
    s.write(b'echo ALIVE2\n')
    out = read_for(s, 4)
    print(f"echo test 2: {repr(out[:200])}")

print("\n=== BT status ===")
cmd(s, 'dmesg | grep -iE "(bluetooth|hci|qca|wcn399)" | tail -30', wait=6)

print("\n=== ath10k/WiFi status ===")
cmd(s, 'dmesg | grep -iE "(ath10k|wlan|snoc|qrtr|rf_clk)" | tail -30', wait=6)

print("\n=== Loaded modules ===")
cmd(s, 'lsmod | grep -E "(ath10k|bluetooth|hci)" 2>/dev/null || cat /proc/modules | grep -E "(ath10k|bluetooth)" | head -10', wait=5)

print("\n=== RF_CLK2 enable count ===")
cmd(s, 'cat /sys/kernel/debug/clk/rf_clk2/clk_enable_count 2>/dev/null || echo "debugfs not mounted"', wait=5)
cmd(s, 'mount -t debugfs none /sys/kernel/debug 2>/dev/null; cat /sys/kernel/debug/clk/rf_clk2/clk_enable_count 2>/dev/null || echo "rf_clk2 not found"', wait=5)

print("\n=== BT regulators ===")
cmd(s, 'for r in vreg_l12a_1p8 vreg_l7a_1p8 vreg_l2c_1p3 vreg_l11c_3p3; do echo -n "$r: "; cat /sys/kernel/debug/regulator/$r/enable 2>/dev/null || echo "not found"; done', wait=8)

print("\n=== hci0 state ===")
cmd(s, 'hciconfig hci0 2>/dev/null || cat /sys/class/bluetooth/hci0/type 2>/dev/null || echo "no hci0"', wait=5)

print("\n=== ttyHS1 pinctrl ===")
cmd(s, 'cat /sys/bus/platform/devices/c8c000.serial/driver 2>/dev/null; ls /sys/bus/platform/devices/ | grep c8c', wait=5)

print("\n=== Full late dmesg (last 50 lines) ===")
cmd(s, 'dmesg | tail -50', wait=8)

s.close()
print("\nDone.")
