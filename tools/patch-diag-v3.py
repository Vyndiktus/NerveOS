#!/usr/bin/env python3
"""
Extend PRE-LINK diagnostic to show HW_VER, REG_UFS_CFG0 (PA link startup timer),
and DME_VS_CORE_CLK_CTRL. Also set CFG0 to 3s to test if short timer is the cause.
"""
import sys

path = '/opt/hiveos/build/cepheus/build/linux-4a8d88483/drivers/ufs/host/ufs-qcom.c'
with open(path) as f:
    text = f.read()

old = (
    '\t\t/* PRE-LINK diagnostic: log TX_FSM and PHY state (HCE done, UIC ready) */\n'
    '\t\t{\n'
    '\t\t\tu32 tx_fsm = 0, uecpa = 0;\n'
    '\t\t\tufshcd_dme_get(hba, UIC_ARG_MIB_SEL(MPHY_TX_FSM_STATE,\n'
    '\t\t\t\tUIC_ARG_MPHY_TX_GEN_SEL_INDEX(0)), &tx_fsm);\n'
    '\t\t\tuecpa = ufshcd_readl(hba, REG_UIC_ERROR_CODE_PHY_ADAPTER_LAYER);\n'
    '\t\t\tdev_err(hba->dev, "PRE-LINK: TX_FSM=%u UECPA=0x%x IS=0x%x\\n",\n'
    '\t\t\t\ttx_fsm, uecpa,\n'
    '\t\t\t\tufshcd_readl(hba, REG_INTERRUPT_STATUS));\n'
    '\t\t}\n'
)

new = (
    '\t\t/* PRE-LINK diagnostic + set PA link startup timer explicitly */\n'
    '\t\t{\n'
    '\t\t\tu32 tx_fsm = 0, uecpa = 0, cfg0, hw_ver, dme_clk = 0;\n'
    '\t\t\tufshcd_dme_get(hba, UIC_ARG_MIB_SEL(MPHY_TX_FSM_STATE,\n'
    '\t\t\t\tUIC_ARG_MPHY_TX_GEN_SEL_INDEX(0)), &tx_fsm);\n'
    '\t\t\tufshcd_dme_get(hba, UIC_ARG_MIB(DME_VS_CORE_CLK_CTRL), &dme_clk);\n'
    '\t\t\tuecpa = ufshcd_readl(hba, REG_UIC_ERROR_CODE_PHY_ADAPTER_LAYER);\n'
    '\t\t\tcfg0 = ufshcd_readl(hba, REG_UFS_CFG0);\n'
    '\t\t\thw_ver = ufshcd_readl(hba, REG_UFS_HW_VERSION);\n'
    '\t\t\t/* Set to 3s (900M cycles @ 300MHz) to rule out timer-too-short */\n'
    '\t\t\tufshcd_writel(hba, 900000000U, REG_UFS_CFG0);\n'
    '\t\t\tdev_err(hba->dev,\n'
    '\t\t\t\t"PRE-LINK: TX_FSM=%u UECPA=0x%x IS=0x%x CFG0=0x%x HW_VER=0x%x DME_CLK=0x%x\\n",\n'
    '\t\t\t\ttx_fsm, uecpa,\n'
    '\t\t\t\tufshcd_readl(hba, REG_INTERRUPT_STATUS),\n'
    '\t\t\t\tcfg0, hw_ver, dme_clk);\n'
    '\t\t}\n'
)

if old not in text:
    print('ERROR: PRE-LINK diagnostic block not found')
    sys.exit(1)

text = text.replace(old, new, 1)
with open(path, 'w') as f:
    f.write(text)
print('PRE-LINK diagnostic extended + CFG0 set to 3s timer')
