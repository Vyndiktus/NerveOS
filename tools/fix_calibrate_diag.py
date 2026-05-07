#!/usr/bin/env python3
path = '/opt/nerveos/build/cepheus/build/linux-4a8d88483/drivers/phy/qualcomm/phy-qcom-qmp-ufs.c'
with open(path, 'r') as f:
    text = f.read()

old = (
    '\tstruct qmp_ufs *qmp = phy_get_drvdata(phy);\n'
    '\t/*\n'
    '\t * SM8150 QMP UFS PHY (V3 hardware): PCS offset 0xC8 = TX_LANE_ENABLE (V3 hardware).\n'
    '\t * The vendor kernel explicitly sets this to 1 in link_startup PRE_CHANGE\n'
    '\t * via ufs_qcom_phy_set_tx_lane_enable(). HCE or BCR reset clears it;\n'
    '\t * without re-enabling, the host M-PHY TX cannot drive link startup.\n'
    '\t */\n'
    '\twritel(0x01, qmp->pcs + 0x0C8);\n'
    '\treturn 0;\n'
    '}'
)

new = (
    '\tstruct qmp_ufs *qmp = phy_get_drvdata(phy);\n'
    '\tu32 before, after;\n'
    '\tbefore = readl(qmp->pcs + 0x0C8);\n'
    '\twritel(0x01, qmp->pcs + 0x0C8);\n'
    '\tafter = readl(qmp->pcs + 0x0C8);\n'
    '\tdev_err(qmp->dev, "qmp_ufs_calibrate: PCS+0xC8 before=0x%x after=0x%x\\n", before, after);\n'
    '\treturn 0;\n'
    '}'
)

if old not in text:
    print('ERROR: old block not found')
    idx = text.find('qmp_ufs_calibrate')
    print(repr(text[idx:idx+400]))
    import sys; sys.exit(1)

text = text.replace(old, new, 1)
with open(path, 'w') as f:
    f.write(text)
print('Diagnostic added to qmp_ufs_calibrate OK')
