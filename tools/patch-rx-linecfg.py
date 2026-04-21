#!/usr/bin/env python3
"""
Fix SM8150 UFS link startup: enable RX LineCfg in QMP PHY before DME_LINK_STARTUP.

Root cause: after BCR reset + V4 PHY init, LINECFG_DISABLE register (PCS+0x148)
bit 1 (RX_LINECFG_DISABLE) may be set, preventing the device M-PHY from receiving
the host's link startup sequence. This causes T_TxActivate timeout (UECPA=0x80000010).

Vendor kernel (cepheus-q-oss, phy-qcom-ufs-qmp-v4.c) explicitly calls
ufs_qcom_phy_ctrl_rx_linecfg(phy, true) before every DME_LINK_STARTUP to clear
this bit. Mainline never does this.

Fix: update qmp_ufs_calibrate() to clear bit 1 of PCS+0x148 (QPHY_V4_PCS_UFS_LINECFG_DISABLE).
"""

import sys

phy_path = '/opt/hiveos/build/cepheus/build/linux-4a8d88483/drivers/phy/qualcomm/phy-qcom-qmp-ufs.c'
with open(phy_path, 'r') as f:
    text = f.read()

# Replace the current diagnostic calibrate function with the correct RX LineCfg enable
old = (
    'static int qmp_ufs_calibrate(struct phy *phy)\n'
    '{\n'
    '\tstruct qmp_ufs *qmp = phy_get_drvdata(phy);\n'
    '\tu32 before, after;\n'
    '\tbefore = readl(qmp->pcs + 0x0C8);\n'
    '\twritel(0x01, qmp->pcs + 0x0C8);\n'
    '\tafter = readl(qmp->pcs + 0x0C8);\n'
    '\tdev_err(qmp->dev, "qmp_ufs_calibrate: PCS+0xC8 before=0x%x after=0x%x\\n", before, after);\n'
    '\treturn 0;\n'
    '}'
)

new = (
    'static int qmp_ufs_calibrate(struct phy *phy)\n'
    '{\n'
    '\tstruct qmp_ufs *qmp = phy_get_drvdata(phy);\n'
    '\tu32 val;\n'
    '\t/*\n'
    '\t * SM8150 V4 QMP UFS PHY: after BCR reset + PHY init, the\n'
    '\t * LINECFG_DISABLE register (PCS+0x148) may have bit 1 set,\n'
    '\t * disabling RX LineCfg and preventing the device M-PHY from\n'
    '\t * receiving DME_LINK_STARTUP frames (T_TxActivate timeout).\n'
    '\t * Vendor kernel clears this in ufs_qcom_phy_ctrl_rx_linecfg().\n'
    '\t */\n'
    '\tval = readl(qmp->pcs + 0x148);\n'
    '\tval &= ~BIT(1);\n'
    '\twritel(val, qmp->pcs + 0x148);\n'
    '\treturn 0;\n'
    '}'
)

if old not in text:
    print('ERROR: diagnostic calibrate block not found')
    idx = text.find('qmp_ufs_calibrate')
    if idx >= 0:
        print(repr(text[idx:idx+500]))
    sys.exit(1)

text = text.replace(old, new, 1)
with open(phy_path, 'w') as f:
    f.write(text)

print('RX LineCfg fix applied to qmp_ufs_calibrate OK')
print('Verify: LINECFG_DISABLE clear present:', '0x148' in text and 'BIT(1)' in text)
