#!/usr/bin/env python3
"""Transfer hci-mgmt ARM64 binary to device via COM3 serial, then run it."""
import serial, time, base64, sys, subprocess

BINARY_PATH_WSL = "/tmp/hci-mgmt"
COM_PORT = "COM3"
BAUD = 115200

def run_wsl(cmd):
    r = subprocess.run(["wsl", "-d", "Debian", "-u", "root", "--", "bash", "-c", cmd],
                       capture_output=True, text=True)
    return r.stdout.strip()

def send_cmd(ser, cmd, wait=2):
    ser.write((cmd + "\n").encode())
    ser.flush()
    time.sleep(wait)
    out = b""
    while ser.in_waiting:
        chunk = ser.read(ser.in_waiting)
        out += chunk
        sys.stdout.buffer.write(chunk)
        sys.stdout.buffer.flush()
        time.sleep(0.1)
    return out.decode(errors="replace")

def main():
    print(f"Reading {BINARY_PATH_WSL} from WSL...")
    b64_data = run_wsl(f"base64 -w 0 {BINARY_PATH_WSL}")
    if not b64_data:
        print("ERROR: Could not read binary from WSL")
        sys.exit(1)
    print(f"Binary base64 length: {len(b64_data)} chars")

    ser = serial.Serial(COM_PORT, BAUD, timeout=1)
    print(f"Opened {COM_PORT}")

    ser.write(b"\n")
    time.sleep(0.5)
    ser.read(ser.in_waiting)

    send_cmd(ser, "rm -f /tmp/hmb64 /tmp/hci-mgmt", wait=1)

    CHUNK = 300
    chunks = [b64_data[i:i+CHUNK] for i in range(0, len(b64_data), CHUNK)]
    print(f"Sending {len(chunks)} chunks...")

    for i, chunk in enumerate(chunks):
        ser.write((f"printf '%s' '{chunk}' >> /tmp/hmb64\n").encode())
        ser.flush()
        time.sleep(0.05)
        ser.read(ser.in_waiting)
        if (i + 1) % 100 == 0:
            print(f"  {i+1}/{len(chunks)}")

    print("Transfer complete. Decoding...")
    send_cmd(ser, "base64 -d /tmp/hmb64 > /tmp/hci-mgmt && chmod +x /tmp/hci-mgmt", wait=2)
    send_cmd(ser, "ls -lh /tmp/hci-mgmt", wait=1)

    # Enable BT dynamic debug so kernel BT messages appear in dmesg
    print("\nEnabling BT dynamic debug...")
    send_cmd(ser, "echo 'module bluetooth +p' > /sys/kernel/debug/dynamic_debug/control 2>/dev/null || true", wait=1)
    send_cmd(ser, "echo 'module btqca +p' > /sys/kernel/debug/dynamic_debug/control 2>/dev/null || true", wait=1)
    send_cmd(ser, "echo 'module hci_uart +p' > /sys/kernel/debug/dynamic_debug/control 2>/dev/null || true", wait=1)

    # Baseline dmesg + sysfs before running
    print("\nBaseline hci0 state:")
    send_cmd(ser, "ls /sys/class/bluetooth/hci0/ 2>/dev/null || echo 'no hci0 sysfs'", wait=1)
    send_cmd(ser, "cat /sys/class/bluetooth/hci0/address 2>/dev/null || echo 'no address'", wait=1)

    # Run hci-mgmt; step 3 now uses HCIDEVUP ioctl (sync, gives real errno)
    print("\nRunning hci-mgmt on hci0...")
    send_cmd(ser, "/tmp/hci-mgmt 0", wait=30)

    # Post-run diagnostics
    print("\n--- hci0 state after hci-mgmt ---")
    send_cmd(ser, "ls /sys/class/bluetooth/hci0/", wait=2)
    send_cmd(ser, "cat /sys/class/bluetooth/hci0/address 2>/dev/null || echo 'no address attr'", wait=1)
    send_cmd(ser, "cat /sys/class/bluetooth/hci0/name 2>/dev/null || echo 'no name attr'", wait=1)
    send_cmd(ser, "cat /sys/class/bluetooth/hci0/type 2>/dev/null || echo 'no type attr'", wait=1)

    print("\n--- dmesg BT/HCI tail ---")
    send_cmd(ser, "dmesg | grep -iE 'hci|bluetooth|qca|wcn|bt_' | tail -20", wait=3)

    ser.close()
    print("\nDone.")

if __name__ == "__main__":
    main()
