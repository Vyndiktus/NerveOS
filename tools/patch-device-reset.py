#!/usr/bin/env python3
"""Remove the bootloader_phy_preserved guard from ufs_qcom_device_reset.
The device reset via GPIO 175 is needed after HIBERNATE_ENTER fails,
to put the UFS device back to a known (DISABLED) state."""

path = '/opt/nerveos/build/cepheus/build/linux-4a8d88483/drivers/ufs/host/ufs-qcom.c'
with open(path, 'r') as f:
    content = f.read()

old = ('\t/* Skip device reset on first boot: bootloader already initialized the device */\n'
       '\tif (host->bootloader_phy_preserved)\n'
       '\t\treturn -EOPNOTSUPP;\n'
       '\n')
new = ''

if old in content:
    content = content.replace(old, new, 1)
    with open(path, 'w') as f:
        f.write(content)
    print('PATCHED OK')
else:
    print('PATTERN NOT FOUND')
