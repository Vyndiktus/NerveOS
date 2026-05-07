#!/usr/bin/env python3
"""
Fix SM8150 UFS link startup: add TX_LANE_ENABLE write before each link startup.

The vendor kernel (cepheus-q-oss) calls ufs_qcom_phy_set_tx_lane_enable(phy, 1)
in link_startup_notify PRE_CHANGE. This writes 0x01 to the QMP PHY PCS register
at offset 0xC8 (TX_LANE_ENABLE). Without this, the M-PHY TX lane is disabled and
the host cannot drive the link startup sequence, causing T_TxActivate timeout.

Two changes:
1. phy-qcom-qmp-ufs.c: add qmp_ufs_calibrate() that writes PCS+0xC8 = 1,
   register as .calibrate in phy_ops.
2. ufs-qcom.c: call phy_calibrate(host->generic_phy) in link_startup PRE_CHANGE,
   and remove the crashing ioremap diagnostic.
"""

import sys

# ── Change 1: phy-qcom-qmp-ufs.c ──────────────────────────────────────────
phy_path = '/opt/nerveos/build/cepheus/build/linux-4a8d88483/drivers/phy/qualcomm/phy-qcom-qmp-ufs.c'
with open(phy_path, 'rb') as f:
    phy_data = f.read()

# Add qmp_ufs_calibrate before the phy_ops struct
old_ops = (
    b'static const struct phy_ops qcom_qmp_ufs_phy_ops = {\n'
    b'\t.power_on\t= qmp_ufs_enable,\n'
    b'\t.power_off\t= qmp_ufs_disable,\n'
    b'\t.set_mode\t= qmp_ufs_set_mode,\n'
    b'\t.owner\t\t= THIS_MODULE,\n'
    b'};\n'
)
new_ops = (
    b'static int qmp_ufs_calibrate(struct phy *phy)\n'
    b'{\n'
    b'\tstruct qmp_ufs *qmp = phy_get_drvdata(phy);\n'
    b'\t/*\n'
    b'\t * SM8150 QMP UFS PHY (V3 hardware): PCS offset 0xC8 = TX_LANE_ENABLE.\n'
    b'\t * The vendor kernel explicitly sets this to 1 in link_startup PRE_CHANGE\n'
    b'\t * via ufs_qcom_phy_set_tx_lane_enable(). HCE or BCR reset clears it;\n'
    b'\t * without re-enabling, the host M-PHY TX cannot drive link startup.\n'
    b'\t */\n'
    b'\twritel(0x01, qmp->pcs + 0x0C8);\n'
    b'\treturn 0;\n'
    b'}\n'
    b'\n'
    b'static const struct phy_ops qcom_qmp_ufs_phy_ops = {\n'
    b'\t.power_on\t= qmp_ufs_enable,\n'
    b'\t.power_off\t= qmp_ufs_disable,\n'
    b'\t.set_mode\t= qmp_ufs_set_mode,\n'
    b'\t.calibrate\t= qmp_ufs_calibrate,\n'
    b'\t.owner\t\t= THIS_MODULE,\n'
    b'};\n'
)

if old_ops not in phy_data:
    print('ERROR: phy_ops not found in QMP driver')
    sys.exit(1)

phy_data = phy_data.replace(old_ops, new_ops, 1)
with open(phy_path, 'wb') as f:
    f.write(phy_data)
print('Change 1: qmp_ufs_calibrate added to phy-qcom-qmp-ufs.c')

# ── Change 2: ufs-qcom.c ──────────────────────────────────────────────────
ufs_path = '/opt/nerveos/build/cepheus/build/linux-4a8d88483/drivers/ufs/host/ufs-qcom.c'
with open(ufs_path, 'rb') as f:
    ufs_data = f.read()

# Remove the crashing ioremap diagnostic and replace with phy_calibrate
old_diag = (
    b'\t\tmsleep(150);\n'
    b'\n'
    b'\t\t/* PHY PCS register dump: see hardware state before link startup */\n'
    b'\t\t{\n'
    b'\t\t\tvoid __iomem *phy_pcs = ioremap(0x1d87c00, 0x200);\n'
    b'\t\t\tvoid __iomem *phy_base = ioremap(0x1d87000, 0x200);\n'
    b'\t\t\tif (phy_pcs && phy_base) {\n'
    b'\t\t\t\tdev_err(hba->dev,\n'
    b'\t\t\t\t\t"PHY_PCS: START=0x%x PWRDN=0x%x SWRST=0x%x READY=0x%x MULTILANE=0x%x\\n",\n'
    b'\t\t\t\t\treadb(phy_pcs + 0x000),\n'
    b'\t\t\t\t\treadb(phy_pcs + 0x004),\n'
    b'\t\t\t\t\treadb(phy_pcs + 0x008),\n'
    b'\t\t\t\t\treadb(phy_pcs + 0x180),\n'
    b'\t\t\t\t\treadb(phy_pcs + 0x1e0));\n'
    b'\t\t\t\tdev_err(hba->dev,\n'
    b'\t\t\t\t\t"PHY_PCS+C8=0x%x PHY_BASE+C8=0x%x\\n",\n'
    b'\t\t\t\t\treadb(phy_pcs + 0x0c8),\n'
    b'\t\t\t\t\treadb(phy_base + 0x0c8));\n'
    b'\t\t\t\tiounmap(phy_pcs);\n'
    b'\t\t\t\tiounmap(phy_base);\n'
    b'\t\t\t}\n'
    b'\t\t}\n'
    b'\n'
    b'\t\t/*\n'
    b'\t\t * Set PA_TActivate per Qualcomm vendor kernel requirement.\n'
)
new_diag = (
    b'\t\tmsleep(150);\n'
    b'\n'
    b'\t\t/*\n'
    b'\t\t * Re-enable TX lane 0 in the QMP PHY PCS before link startup.\n'
    b'\t\t * SM8150 V3 PHY: PCS offset 0xC8 = TX_LANE_ENABLE. HCE resets this;\n'
    b'\t\t * without it, the host M-PHY TX cannot drive the activation sequence.\n'
    b'\t\t * Vendor kernel does this via ufs_qcom_phy_set_tx_lane_enable().\n'
    b'\t\t */\n'
    b'\t\tphy_calibrate(host->generic_phy);\n'
    b'\n'
    b'\t\t/*\n'
    b'\t\t * Set PA_TActivate per Qualcomm vendor kernel requirement.\n'
)

if old_diag not in ufs_data:
    print('ERROR: ioremap diagnostic block not found in ufs-qcom.c')
    idx = ufs_data.find(b'ioremap(0x1d87c00')
    print(f'  ioremap found at: {idx}')
    sys.exit(1)

ufs_data = ufs_data.replace(old_diag, new_diag, 1)
with open(ufs_path, 'wb') as f:
    f.write(ufs_data)
print('Change 2: phy_calibrate() added to ufs-qcom.c link_startup PRE_CHANGE')

print('\nVerification:')
print('  qmp_ufs_calibrate defined:', b'qmp_ufs_calibrate' in phy_data)
print('  .calibrate in phy_ops:', b'.calibrate\t= qmp_ufs_calibrate' in phy_data)
print('  phy_calibrate() in ufs-qcom.c:', b'phy_calibrate(host->generic_phy)' in ufs_data)
print('  ioremap removed:', b'ioremap(0x1d87c00' not in ufs_data)
