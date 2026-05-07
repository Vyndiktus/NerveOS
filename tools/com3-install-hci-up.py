#!/usr/bin/env python3
"""Transfer hci-up ARM64 binary to device via COM3 serial, then run it."""
import serial, time, base64, sys, subprocess, os

BINARY_PATH_WSL = "/tmp/hci-up"
COM_PORT = "COM3"
BAUD = 115200

def run_wsl(cmd):
    r = subprocess.run(["wsl", "-d", "Debian", "-u", "root", "--", "bash", "-c", cmd],
                       capture_output=True, text=True)
    return r.stdout.strip()

def wait_prompt(ser, timeout=10):
    deadline = time.time() + timeout
    buf = b""
    while time.time() < deadline:
        chunk = ser.read(ser.in_waiting or 1)
        if chunk:
            buf += chunk
            sys.stdout.buffer.write(chunk)
            sys.stdout.buffer.flush()
            if buf.endswith(b"# ") or buf.endswith(b"$ "):
                return True
    return False

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
    # Read binary from WSL
    print(f"Reading {BINARY_PATH_WSL} from WSL...")
    b64_data = run_wsl(f"base64 -w 0 {BINARY_PATH_WSL}")
    if not b64_data:
        print("ERROR: Could not read binary from WSL")
        sys.exit(1)
    print(f"Binary base64 length: {len(b64_data)} chars")

    ser = serial.Serial(COM_PORT, BAUD, timeout=1)
    print(f"Opened {COM_PORT}")

    # Wake prompt
    ser.write(b"\n")
    time.sleep(0.5)
    ser.read(ser.in_waiting)

    # Clear any previous transfer
    send_cmd(ser, "rm -f /tmp/hciup64 /tmp/hci-up", wait=1)

    # Split into chunks and send
    CHUNK = 300
    chunks = [b64_data[i:i+CHUNK] for i in range(0, len(b64_data), CHUNK)]
    print(f"Sending {len(chunks)} chunks of {CHUNK} chars each...")

    for i, chunk in enumerate(chunks):
        cmd = f"printf '%s' '{chunk}' >> /tmp/hciup64"
        ser.write((cmd + "\n").encode())
        ser.flush()
        time.sleep(0.05)
        ser.read(ser.in_waiting)  # drain echo
        if (i + 1) % 50 == 0:
            print(f"  {i+1}/{len(chunks)} chunks sent")

    print("Transfer complete. Decoding and installing...")
    send_cmd(ser, "base64 -d /tmp/hciup64 > /tmp/hci-up && chmod +x /tmp/hci-up", wait=2)
    send_cmd(ser, "ls -lh /tmp/hci-up", wait=1)
    send_cmd(ser, "file /tmp/hci-up 2>/dev/null || echo 'file cmd not available'", wait=1)

    print("\nRunning hci-up on hci0...")
    send_cmd(ser, "/tmp/hci-up 0", wait=5)

    ser.close()
    print("\nDone.")

if __name__ == "__main__":
    main()
