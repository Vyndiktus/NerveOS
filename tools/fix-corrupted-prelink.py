#!/usr/bin/env python3
"""Remove the corrupted PRE-LINK block and re-apply it correctly."""

path = '/opt/nerveos/build/cepheus/build/linux-4a8d88483/drivers/ufs/host/ufs-qcom.c'
with open(path, 'rb') as f:
    data = f.read()

# Remove the corrupted block (has literal '+ msg + b' in C code)
corrupted = (
    b'\n'
    b'\t\t/* Diagnostic: log TX_FSM_STATE and UECPA before DME_LINK_STARTUP */\n'
    b'\t\t{\n'
    b'\t\t\tu32 tx_fsm = 0, uecpa = 0;\n'
    b'\t\t\tufshcd_dme_get(hba, UIC_ARG_MIB_SEL(MPHY_TX_FSM_STATE,\n'
    b'\t\t\t\tUIC_ARG_MPHY_TX_GEN_SEL_INDEX(0)), &tx_fsm);\n'
    b'\t\t\tuecpa = ufshcd_readl(hba, REG_UIC_ERROR_CODE_PHY_ADAPTER_LAYER);\n'
    b'\t\t\tdev_err(hba->dev,  + msg + b,\n'
    b'\t\t\t\ttx_fsm, uecpa,\n'
    b'\t\t\t\tufshcd_readl(hba, REG_INTERRUPT_STATUS));\n'
    b'\t\t}\n'
)

if corrupted in data:
    data = data.replace(corrupted, b'\n', 1)
    print('Corrupted block removed')
else:
    print('Corrupted block not found (exact match failed)')
    idx = data.find(b'+ msg + b')
    if idx >= 0:
        print('Found at:', idx)
        print('Context:', repr(data[idx-200:idx+50]))
    exit(1)

# Now inject the correct PRE-LINK diagnostic
target = b'\t\terr = ufs_qcom_enable_lane_clks(host);\n\t\tbreak;\n'
fmt = b'PRE-LINK: TX_FSM=%u UECPA=0x%x IS=0x%x\\n'

prelink = (
    b'\t\terr = ufs_qcom_enable_lane_clks(host);\n'
    b'\n'
    b'\t\t/* Diagnostic: log TX_FSM_STATE and UECPA before DME_LINK_STARTUP */\n'
    b'\t\t{\n'
    b'\t\t\tu32 tx_fsm = 0, uecpa = 0;\n'
    b'\t\t\tufshcd_dme_get(hba, UIC_ARG_MIB_SEL(MPHY_TX_FSM_STATE,\n'
    b'\t\t\t\tUIC_ARG_MPHY_TX_GEN_SEL_INDEX(0)), &tx_fsm);\n'
    b'\t\t\tuecpa = ufshcd_readl(hba, REG_UIC_ERROR_CODE_PHY_ADAPTER_LAYER);\n'
    b'\t\t\tdev_err(hba->dev, "' + fmt + b'",\n'
    b'\t\t\t\ttx_fsm, uecpa,\n'
    b'\t\t\t\tufshcd_readl(hba, REG_INTERRUPT_STATUS));\n'
    b'\t\t}\n'
    b'\t\tbreak;\n'
)

if target not in data:
    print('ERROR: lane_clks injection point not found after cleanup')
    exit(1)

data = data.replace(target, prelink, 1)
with open(path, 'wb') as f:
    f.write(data)
print('PRE-LINK re-applied correctly')
print('PRE-LINK present:', b'PRE-LINK' in data)
print('Corrupted code gone:', b'+ msg + b' not in data)
