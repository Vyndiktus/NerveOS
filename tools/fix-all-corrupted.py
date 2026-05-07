#!/usr/bin/env python3
"""Strip ALL corrupted PRE-LINK blocks and re-apply once cleanly."""

path = '/opt/nerveos/build/cepheus/build/linux-4a8d88483/drivers/ufs/host/ufs-qcom.c'
with open(path, 'rb') as f:
    data = f.read()

# Remove any block containing '+ msg + b' (corrupted Python literal)
import re
# Pattern: the diagnostic block with corrupted dev_err
corrupted_pattern = (
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

count = data.count(corrupted_pattern)
print(f'Found {count} corrupted block(s)')
while corrupted_pattern in data:
    data = data.replace(corrupted_pattern, b'\n', 1)

print('After removal, + msg + b still present:', b'+ msg + b' in data)

# Verify clean injection point
target = b'\t\terr = ufs_qcom_enable_lane_clks(host);\n\t\tbreak;\n'
if target not in data:
    print('ERROR: injection point still not found - showing context:')
    idx = data.find(b'enable_lane_clks(host)')
    print(repr(data[idx-10:idx+100]))
    with open(path, 'wb') as f:
        f.write(data)
    exit(1)

# Inject correct PRE-LINK
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

data = data.replace(target, prelink, 1)
with open(path, 'wb') as f:
    f.write(data)
print('PRE-LINK applied cleanly')
print('PRE-LINK present:', b'PRE-LINK' in data)
print('Corrupted code gone:', b'+ msg + b' not in data)
