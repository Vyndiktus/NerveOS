#!/usr/bin/env python3
"""Remove PRE-LINK diagnostic entirely to test if it's causing the hang."""

path = '/opt/hiveos/build/cepheus/build/linux-4a8d88483/drivers/ufs/host/ufs-qcom.c'
with open(path, 'rb') as f:
    data = f.read()

# Remove the entire PRE-LINK diagnostic block
old = (b'\n\t\t/* Diagnostic: log TX_FSM_STATE and UECPA before DME_LINK_STARTUP */\n'
       b'\t\t{\n'
       b'\t\t\tu32 tx_fsm = 0, uecpa = 0;\n'
       b'\t\t\tufshcd_dme_get(hba, UIC_ARG_MIB_SEL(MPHY_TX_FSM_STATE,\n'
       b'\t\t\t\tUIC_ARG_MPHY_TX_GEN_SEL_INDEX(0)), &tx_fsm);\n'
       b'\t\t\tuecpa = ufshcd_readl(hba, REG_UIC_ERROR_CODE_PHY_ADAPTER_LAYER);\n'
       b'\t\t\tdev_err(hba->dev, "PRE-LINK: TX_FSM=%u UECPA=0x%x IS=0x%x\\n",\n'
       b'\t\t\t\ttx_fsm, uecpa,\n'
       b'\t\t\t\tufshcd_readl(hba, REG_INTERRUPT_STATUS));\n'
       b'\t\t}\n')

if old in data:
    data = data.replace(old, b'\n', 1)
    with open(path, 'wb') as f:
        f.write(data)
    print('STRIPPED OK - PRE-LINK diagnostic removed')
else:
    idx = data.find(b'PRE-LINK')
    print('Not found, context:')
    if idx >= 0:
        print(repr(data[idx-200:idx+100]))
    else:
        print('PRE-LINK string not found at all')
