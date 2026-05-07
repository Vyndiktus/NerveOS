#!/usr/bin/env python3
"""Patch hci_qca.c: make WCN3990 baudrate vendor event timeout non-fatal."""

HCI_QCA = "/opt/NerveOS/build/cepheus/build/linux-4a8d88483/drivers/bluetooth/hci_qca.c"

with open(HCI_QCA) as f:
    content = f.read()

old = '''\t\t\tif (!wait_for_completion_timeout(&qca->drop_ev_comp,
\t\t\t\t\t\t msecs_to_jiffies(100))) {
\t\t\t\tbt_dev_err(hu->hdev,
\t\t\t\t\t   "Failed to change controller baudrate\\n");
\t\t\t\tret = -ETIMEDOUT;
\t\t\t}'''

new = '''\t\t\tif (!wait_for_completion_timeout(&qca->drop_ev_comp,
\t\t\t\t\t\t msecs_to_jiffies(100))) {
\t\t\t\tbt_dev_warn(hu->hdev,
\t\t\t\t\t    "WCN3990 baudrate event timeout, continuing\\n");
\t\t\t\t/* ROM supports baudrate change without vendor event */
\t\t\t}'''

if old in content:
    content = content.replace(old, new, 1)
    with open(HCI_QCA, "w") as f:
        f.write(content)
    print("hci_qca.c patched: WCN3990 baudrate timeout is now non-fatal")
else:
    print("ERROR: pattern not found — showing context:")
    idx = content.find("Failed to change controller baudrate")
    if idx >= 0:
        print(repr(content[max(0, idx-200):idx+200]))
    import sys; sys.exit(1)
