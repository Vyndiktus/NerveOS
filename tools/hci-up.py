#!/usr/bin/env python3
"""Bring up hci0 and read BD_ADDR via raw HCI socket."""
import socket, struct, time, sys

AF_BLUETOOTH = 31
BTPROTO_HCI = 1
SOCK_RAW = 3
SOL_HCI = 0
HCI_FILTER = 2

HCI_COMMAND_PKT = 0x01
HCI_EVENT_PKT = 0x04

def hci_opcode(ogf, ocf):
    return (ogf << 10) | ocf

OGF_HOST_CTL = 0x03
OCF_RESET = 0x0003
OCF_READ_LOCAL_NAME = 0x0014

OGF_INFO_PARAM = 0x04
OCF_READ_BD_ADDR = 0x0009

def send_cmd(s, ogf, ocf, params=b''):
    op = hci_opcode(ogf, ocf)
    pkt = struct.pack('<BHB', HCI_COMMAND_PKT, op, len(params)) + params
    s.send(pkt)

def recv_event(s, timeout=3):
    s.settimeout(timeout)
    try:
        data = s.recv(1024)
        return data
    except socket.timeout:
        return None

try:
    s = socket.socket(AF_BLUETOOTH, SOCK_RAW, BTPROTO_HCI)
    s.bind((0,))  # hci0

    # Set filter to receive all events
    flt = struct.pack('IQh', 0xffffffff, 0xffffffffffffffff, 0)
    s.setsockopt(SOL_HCI, HCI_FILTER, flt)
except Exception as e:
    print(f"Failed to open HCI socket: {e}")
    sys.exit(1)

print("Sending HCI_Reset...")
send_cmd(s, OGF_HOST_CTL, OCF_RESET)
ev = recv_event(s, 5)
if ev:
    print(f"Reset response: {ev.hex()}")
else:
    print("No response to reset")
    sys.exit(1)

time.sleep(0.5)

print("Reading BD_ADDR...")
send_cmd(s, OGF_INFO_PARAM, OCF_READ_BD_ADDR)
ev = recv_event(s, 3)
if ev and len(ev) >= 12:
    # Event: 04 0e 0a 01 09 10 00 <6 bytes addr>
    addr_bytes = ev[7:13]
    addr = ':'.join(f'{b:02X}' for b in reversed(addr_bytes))
    print(f"BD_ADDR: {addr}")
else:
    print(f"BD_ADDR response: {ev.hex() if ev else 'none'}")

print("Reading local name...")
send_cmd(s, OGF_HOST_CTL, OCF_READ_LOCAL_NAME)
ev = recv_event(s, 3)
if ev and len(ev) > 7:
    name = ev[7:].rstrip(b'\x00').decode(errors='replace')
    print(f"Name: {name!r}")

s.close()
print("Done.")
