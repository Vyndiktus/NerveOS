#!/usr/bin/env python3
path = '/opt/hiveos/build/cepheus/build/linux-4a8d88483/drivers/ufs/host/ufs-qcom.c'
with open(path, 'rb') as f:
    data = f.read()

if b'PRE-LINK' in data:
    print('PRE-LINK already present')
    exit(0)

fmt = b'PRE-LINK: TX_FSM=%u UECPA=0x%x IS=0x%x\\n'
q = bytes([0x22])

target = b'\t\terr = ufs_qcom_enable_lane_clks(host);\n\n\t\tbreak;\n'
prelink = (
    b'\t\terr = ufs_qcom_enable_lane_clks(host);\n\n'
    b'\t\t/* Diagnostic: log TX_FSM_STATE and UECPA before DME_LINK_STARTUP */\n'
    b'\t\t{\n'
    b'\t\t\tu32 tx_fsm = 0, uecpa = 0;\n'
    b'\t\t\tufshcd_dme_get(hba, UIC_ARG_MIB_SEL(MPHY_TX_FSM_STATE,\n'
    b'\t\t\t\tUIC_ARG_MPHY_TX_GEN_SEL_INDEX(0)), &tx_fsm);\n'
    b'\t\t\tuecpa = ufshcd_readl(hba, REG_UIC_ERROR_CODE_PHY_ADAPTER_LAYER);\n'
    b'\t\t\tdev_err(hba->dev, ' + q + fmt + q + b',\n'
    b'\t\t\t\ttx_fsm, uecpa,\n'
    b'\t\t\t\tufshcd_readl(hba, REG_INTERRUPT_STATUS));\n'
    b'\t\t}\n'
    b'\t\tbreak;\n'
)

if target not in data:
    print('ERROR: target not found')
    exit(1)

data = data.replace(target, prelink, 1)
with open(path, 'wb') as f:
    f.write(data)
print('PRE-LINK applied OK')
print('present:', b'PRE-LINK' in data)
