#!/usr/bin/env python3
"""
Add QMP PHY PCS register dump to link_startup_notify PRE_CHANGE.
Reads key PCS registers via ioremap to see actual hardware state.
SM8150 QMP UFS PHY PCS base = PHY base 0x1d87000 + PCS offset 0xC00 = 0x1d87C00.
Vendor kernel's UFS_PHY_TX_LANE_ENABLE = 0xC8 from PHY mmio base = 0x1d870C8 (serdes region).
We also read PCS+0xC8 = 0x1d87CC8 to cover both possibilities.
"""

path = '/opt/nerveos/build/cepheus/build/linux-4a8d88483/drivers/ufs/host/ufs-qcom.c'
with open(path, 'rb') as f:
    data = f.read()

# Insert PHY register dump right before the PA_TActivate DME set
# Target: after msleep(150), before PA_TActivate
old = (
    b'\t\tmsleep(150);\n'
    b'\n'
    b'\t\t/*\n'
    b'\t\t * Set PA_TActivate per Qualcomm vendor kernel requirement.\n'
)
new = (
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

if old not in data:
    print('ERROR: target not found')
    idx = data.find(b'msleep(150)')
    if idx >= 0:
        print(repr(data[idx:idx+200]))
    import sys; sys.exit(1)

data = data.replace(old, new, 1)
with open(path, 'wb') as f:
    f.write(data)

print('PHY register dump patch applied')
print('ioremap present:', b'ioremap(0x1d87c00' in data)
