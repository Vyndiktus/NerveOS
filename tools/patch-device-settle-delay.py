#!/usr/bin/env python3
"""
Add 150ms settling delay in link_startup_notify PRE_CHANGE.
Device reset happens ~12ms before first link startup; UFS spec requires
T_Power-on-reset (10-50ms) before device responds to link startup frames.
"""

path = '/opt/nerveos/build/cepheus/build/linux-4a8d88483/drivers/ufs/host/ufs-qcom.c'
with open(path, 'rb') as f:
    data = f.read()

# Find our PRE-LINK diagnostic insertion point in link_startup_notify
# and add a delay before it (i.e., before the diagnostic and before link startup)
# Target: the disable_host_tx_lcc call + our PRE-LINK diagnostic block
old = (
    b'\t\terr = ufshcd_disable_host_tx_lcc(hba);\n'
    b'\n'
    b'\t\t/* PRE-LINK diagnostic: log TX_FSM and PHY state (HCE done, UIC ready) */\n'
)
new = (
    b'\t\terr = ufshcd_disable_host_tx_lcc(hba);\n'
    b'\n'
    b'\t\t/*\n'
    b'\t\t * Give UFS device time after HCE link drop before we attempt\n'
    b'\t\t * DME_LINK_STARTUP. The device needs T_Power-on-reset (~10-50ms)\n'
    b'\t\t * after the bootloader link was torn down by HCE.\n'
    b'\t\t */\n'
    b'\t\tmsleep(150);\n'
    b'\n'
    b'\t\t/* PRE-LINK diagnostic: log TX_FSM and PHY state (HCE done, UIC ready) */\n'
)

if old not in data:
    print('ERROR: target not found')
    idx = data.find(b'ufshcd_disable_host_tx_lcc')
    print(f'disable_host_tx_lcc at offset {idx}')
    print(repr(data[idx:idx+200]))
    import sys; sys.exit(1)

data = data.replace(old, new, 1)
with open(path, 'wb') as f:
    f.write(data)

print('Delay patch applied OK')
print('msleep(150) present:', b'msleep(150)' in data)
