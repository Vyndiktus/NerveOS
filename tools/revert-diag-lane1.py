#!/usr/bin/env python3
"""Revert lane 1 diagnostic - DME_GET for lane 1 hangs if PHY is single-lane."""

path = '/opt/hiveos/build/cepheus/build/linux-4a8d88483/drivers/ufs/host/ufs-qcom.c'
with open(path, 'rb') as f:
    data = f.read()

old = (b'\t\t/* Diagnostic: log TX_FSM (both lanes) and UECPA before DME_LINK_STARTUP */\n'
       b'\t\t{\n'
       b'\t\t\tu32 tx_fsm0 = 0xff, tx_fsm1 = 0xff, uecpa;\n'
       b'\t\t\tufshcd_dme_get(hba, UIC_ARG_MIB_SEL(MPHY_TX_FSM_STATE,\n'
       b'\t\t\t\tUIC_ARG_MPHY_TX_GEN_SEL_INDEX(0)), &tx_fsm0);\n'
       b'\t\t\tufshcd_dme_get(hba, UIC_ARG_MIB_SEL(MPHY_TX_FSM_STATE,\n'
       b'\t\t\t\tUIC_ARG_MPHY_TX_GEN_SEL_INDEX(1)), &tx_fsm1);\n'
       b'\t\t\tuecpa = ufshcd_readl(hba, REG_UIC_ERROR_CODE_PHY_ADAPTER_LAYER);\n'
       b'\t\t\tdev_err(hba->dev,\n'
       b'\t\t\t\t"PRE-LINK: TX_FSM0=%u TX_FSM1=%u UECPA=0x%x IS=0x%x\\n",\n'
       b'\t\t\t\ttx_fsm0, tx_fsm1, uecpa,\n'
       b'\t\t\t\tufshcd_readl(hba, REG_INTERRUPT_STATUS));\n'
       b'\t\t}')

new = (b'\t\t/* Diagnostic: log TX_FSM and UECPA before DME_LINK_STARTUP */\n'
       b'\t\t{\n'
       b'\t\t\tu32 tx_fsm = 0, uecpa = 0;\n'
       b'\t\t\tufshcd_dme_get(hba, UIC_ARG_MIB_SEL(MPHY_TX_FSM_STATE,\n'
       b'\t\t\t\tUIC_ARG_MPHY_TX_GEN_SEL_INDEX(0)), &tx_fsm);\n'
       b'\t\t\tuecpa = ufshcd_readl(hba, REG_UIC_ERROR_CODE_PHY_ADAPTER_LAYER);\n'
       b'\t\t\tdev_err(hba->dev, "PRE-LINK: TX_FSM=%u UECPA=0x%x IS=0x%x\\n",\n'
       b'\t\t\t\ttx_fsm, uecpa,\n'
       b'\t\t\t\tufshcd_readl(hba, REG_INTERRUPT_STATUS));\n'
       b'\t\t}')

if old in data:
    data = data.replace(old, new, 1)
    with open(path, 'wb') as f:
        f.write(data)
    print('REVERTED OK - back to lane 0 only')
else:
    idx = data.find(b'PRE-LINK: TX_FSM')
    print('Pattern not found, context:')
    print(repr(data[idx-200:idx+100]))
