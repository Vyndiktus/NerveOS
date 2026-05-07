#!/usr/bin/env python3
"""Patch btqca.c to make ENOENT for firmware non-fatal (ROM patch sufficient)."""

BTQCA = "/opt/NerveOS/build/cepheus/build/linux-4a8d88483/drivers/bluetooth/btqca.c"

with open(BTQCA) as f:
    content = f.read()

# The else block that returns error when firmware file is not found
old = '''\t\t} else {
\t\t\tbt_dev_err(hdev, "QCA Failed to request file: %s (%d)",
\t\t\t\t   config->fwname, ret);
\t\t\treturn ret;
\t\t}
\t}'''

new = '''\t\t} else {
\t\t\tif (ret == -ENOENT) {
\t\t\t\tbt_dev_warn(hdev, "QCA %s not found, running with ROM patch",
\t\t\t\t\t    config->fwname);
\t\t\t\treturn 0;
\t\t\t}
\t\t\tbt_dev_err(hdev, "QCA Failed to request file: %s (%d)",
\t\t\t\t   config->fwname, ret);
\t\t\treturn ret;
\t\t}
\t}'''

if old in content:
    content = content.replace(old, new, 1)
    with open(BTQCA, "w") as f:
        f.write(content)
    print("btqca.c patched: ENOENT for firmware is now non-fatal")
else:
    print("ERROR: pattern not found")
    # Show context around the else block
    idx = content.find("QCA Failed to request file")
    if idx >= 0:
        print(repr(content[max(0,idx-100):idx+200]))
    import sys; sys.exit(1)
