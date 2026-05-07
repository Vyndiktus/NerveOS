#!/usr/bin/env python3
"""Deep BT diagnostics — regulators, pinctrl, UART RX path."""
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
    txt = out.decode(errors='replace').strip()
    # Remove echo of command
    if txt.startswith(c[:30]):
        txt = txt[len(c):].lstrip('\r\n')
    print(txt or "(no output)")
    return out

# Wake
s.write(b'\n')
read_for(s, 2)

# Verify alive
s.write(b'echo ALIVE\n')
out = read_for(s, 3)
if b'ALIVE' not in out:
    print("Device not responding!")
    s.close()
    sys.exit(1)
print("Device is alive\n")

# Check regulator sysfs
cmd(s, 'ls /sys/class/regulator/ | head -20', wait=5)
cmd(s, 'for d in /sys/class/regulator/regulator.*; do n=$(cat $d/name 2>/dev/null); if echo "$n" | grep -qiE "(l12a|l7a|l2c|l11c)"; then echo "$n: en=$(cat $d/state 2>/dev/null)"; fi; done', wait=10)

# Check all BT-related regulator state
cmd(s, 'grep -r "" /sys/class/regulator/*/name 2>/dev/null | grep -iE "(l12|l7a|l2c|l11c)" | while read line; do d=$(echo $line | cut -d/ -f5); n=$(cat /sys/class/regulator/$d/name 2>/dev/null); e=$(cat /sys/class/regulator/$d/state 2>/dev/null); echo "$n: $e"; done', wait=10)

# Check dmesg for regulator errors during BT init
cmd(s, 'dmesg | grep -iE "(regulator|vreg|supply|l12a|l7a_1p8)" | head -30', wait=6)

# Check dmesg for BT power and UART errors
cmd(s, 'dmesg | grep -iE "(qca|wcn|hci|uart|hs.*uart|geni.*serial|c8c000)" | head -30', wait=6)

# Check pinctrl for UART13 (c8c000.serial)
cmd(s, 'cat /sys/kernel/debug/pinctrl/*/pinmux-pins 2>/dev/null | grep -A2 -B2 "75\\|76\\|77\\|78" | head -40', wait=6)

# Check GPIO 75-78 mux state
cmd(s, 'for g in 75 76 77 78; do echo -n "GPIO$g: "; cat /sys/kernel/debug/gpio 2>/dev/null | grep "gpio-$g " | head -1 || echo "not found"; done', wait=8)

# Direct pinctrl pins dump
cmd(s, 'cat /sys/kernel/debug/pinctrl/*/pins 2>/dev/null | grep -E "pin (75|76|77|78) " | head -10', wait=6)

# Check if BT device is in platform bus
cmd(s, 'ls /sys/bus/platform/devices/ | grep -iE "(bt|bluetooth|wcn|uart)"', wait=5)

# Check ttyHS1 - is it accessible?
cmd(s, 'ls -la /dev/ttyHS* /dev/ttyMSM* 2>/dev/null', wait=5)

# Try to read ttyHS1 attributes
cmd(s, 'stty -F /dev/ttyHS1 2>/dev/null | head -3 || echo "ttyHS1 not accessible"', wait=5)

# Check GENI serial driver state
cmd(s, 'cat /sys/bus/platform/devices/c8c000.serial/driver 2>/dev/null; ls /sys/bus/platform/devices/c8c000.serial/ 2>/dev/null', wait=5)

# Check for hci0 sysfs (even if unregistered)
cmd(s, 'ls /sys/class/bluetooth/ 2>/dev/null || echo "no bluetooth devices"', wait=5)

# Check dmesg for any regulator bulk_enable errors
cmd(s, 'dmesg | grep -iE "(bulk_enable|regulator_enable|failed.*enable|enable.*failed|ENODEV|EPROBE)" | head -20', wait=6)

# Check the BT serial binding - does kernel see wcn3990-bt?
cmd(s, 'ls /sys/bus/serial/devices/ 2>/dev/null || ls /sys/bus/platform/devices/ | grep -i serial', wait=5)

# Check if WCN3990 BT needs PMIC arbiter
cmd(s, 'dmesg | grep -iE "(spmi|pmic|pm8150|regmap)" | head -20', wait=6)

# Check for any power control GPIO for BT
cmd(s, 'dmesg | grep -iE "(gpio.*bt|bt.*gpio|reset.*bt|bt.*reset)" | head -10', wait=5)

# Try manually writing to ttyHS1 and see if we get anything back
cmd(s, 'dd if=/dev/ttyHS1 of=/dev/null bs=1 count=1 iflag=nonblock 2>&1 || echo "ttyHS1 read status: $?"', wait=5)

# Check full BT dmesg with context
cmd(s, 'dmesg | grep -n -iE "(bluetooth|hci|qca|wcn)" | head -50', wait=8)

s.close()
print("\nDone.")
