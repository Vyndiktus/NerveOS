#!/usr/bin/env python3
"""Add lane 1 TX_FSM to PRE-LINK diagnostic."""

path = '/opt/nerveos/build/cepheus/build/linux-4a8d88483/drivers/ufs/host/ufs-qcom.c'
with open(path, 'rb') as f:
    data = f.read()

old = (b'PRE-LINK: TX_FSM=%u UECPA=0x%x IS=0x%x\\n",\n'
       b'\t\t\t\ttx_fsm, uecpa,\n'
       b'\t\t\t\tufshcd_readl(hba, REG_INTERRUPT_STATUS));')

new = (b'PRE-LINK: TX_FSM0=%u TX_FSM1=%u UECPA=0x%x IS=0x%x\\n",\n'
       b'\t\t\t\ttx_fsm0, tx_fsm1, uecpa,\n'
       b'\t\t\t\tufshcd_readl(hba, REG_INTERRUPT_STATUS));')

# Also replace the variable declarations and second dme_get
old2 = (b'u32 tx_fsm = 0, uecpa = 0;\n'
        b'\t\t\tufshcd_dme_get(hba, UIC_ARG_MIB_SEL(MPHY_TX_FSM_STATE,\n'
        b'\t\t\t\tUIC_ARG_MPHY_TX_GEN_SEL_INDEX(0)), &tx_fsm);\n'
        b'\t\t\tuecpa = ufshcd_readl(hba, REG_UIC_ERROR_CODE_PHY_ADAPTER_LAYER);\n'
        b'\t\t\tdev_err(hba->dev, "')

new2 = (b'u32 tx_fsm0 = 0xff, tx_fsm1 = 0xff, uecpa;\n'
        b'\t\t\tufshcd_dme_get(hba, UIC_ARG_MIB_SEL(MPHY_TX_FSM_STATE,\n'
        b'\t\t\t\tUIC_ARG_MPHY_TX_GEN_SEL_INDEX(0)), &tx_fsm0);\n'
        b'\t\t\tufshcd_dme_get(hba, UIC_ARG_MIB_SEL(MPHY_TX_FSM_STATE,\n'
        b'\t\t\t\tUIC_ARG_MPHY_TX_GEN_SEL_INDEX(1)), &tx_fsm1);\n'
        b'\t\t\tuecpa = ufshcd_readl(hba, REG_UIC_ERROR_CODE_PHY_ADAPTER_LAYER);\n'
        b'\t\t\tdev_err(hba->dev,\n'
        b'\t\t\t\t"')

if old2 in data and old in data:
    data = data.replace(old2, new2, 1)
    data = data.replace(old, new, 1)
    with open(path, 'wb') as f:
        f.write(data)
    print('PATCHED OK')
else:
    print('old2 found:', old2 in data)
    print('old found:', old in data)
    idx = data.find(b'PRE-LINK')
    print(repr(data[idx-200:idx+100]))
