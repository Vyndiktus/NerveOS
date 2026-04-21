#!/usr/bin/env python3
"""
Restore msleep(150) before PA_TActivate in link_startup_notify PRE_CHANGE.
The delay was removed when patch-link-startup-fixes.py replaced the
"msleep(150) + PRE-LINK comment" block with the PA_TActivate block.
Device reset (GPIO, 25µs pulse) happens ~13ms before link startup;
UFS spec requires T_Power-on-reset (10-50ms, practical >100ms) before
the device M-PHY TX responds to link startup frames.
"""

path = '/opt/hiveos/build/cepheus/build/linux-4a8d88483/drivers/ufs/host/ufs-qcom.c'
with open(path, 'rb') as f:
    data = f.read()

old = (
    b'\t\t/*\n'
    b'\t\t * Give UFS device time after HCE link drop before we attempt\n'
    b'\t\t * DME_LINK_STARTUP. The device needs T_Power-on-reset (~10-50ms)\n'
    b'\t\t * after the bootloader link was torn down by HCE.\n'
    b'\t\t */\n'
    b'\t\t/*\n'
    b'\t\t * Set PA_TActivate per Qualcomm vendor kernel requirement.\n'
    b'\t\t * Without this, T_TxActivate timer may expire during link startup.\n'
    b'\t\t */\n'
    b'\t\tufshcd_dme_set(hba, UIC_ARG_MIB(PA_TACTIVATE), 10);\n'
)
new = (
    b'\t\t/*\n'
    b'\t\t * Device reset (GPIO pulse) happens ~13ms before this point.\n'
    b'\t\t * UFS spec T_Power-on-reset requires 10-50ms (practical: 100ms+)\n'
    b'\t\t * before the device M-PHY TX responds to DME_LINK_STARTUP.\n'
    b'\t\t */\n'
    b'\t\tmsleep(150);\n'
    b'\n'
    b'\t\t/*\n'
    b'\t\t * Set PA_TActivate per Qualcomm vendor kernel requirement.\n'
    b'\t\t * Without this, T_TxActivate timer may expire during link startup.\n'
    b'\t\t */\n'
    b'\t\tufshcd_dme_set(hba, UIC_ARG_MIB(PA_TACTIVATE), 10);\n'
)

if old not in data:
    print('ERROR: target block not found')
    idx = data.find(b'PA_TACTIVATE), 10')
    if idx >= 0:
        print(repr(data[idx-300:idx+50]))
    import sys; sys.exit(1)

data = data.replace(old, new, 1)
with open(path, 'wb') as f:
    f.write(data)

print('Settle delay restored OK')
print('msleep(150) present:', b'msleep(150)' in data)
print('PA_TActivate present:', b'PA_TACTIVATE), 10' in data)
