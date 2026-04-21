#!/usr/bin/env python3
"""
Fix: enable device M-PHY reference clock (REG_UFS_CFG1 BIT(26)) after core reset.

Root cause of PA_GENERIC_ERROR / T_TxActivate failure on SM8150:
- ufs_qcom_host_reset() triggers a GCC peripheral reset which resets ALL host
  controller registers to hardware defaults, including REG_UFS_CFG1 BIT(26).
- BIT(26) enables the reference clock output from the host controller to the
  UFS device M-PHY. Without it the device M-PHY has no clock reference and
  cannot complete T_TxActivate → UECPA=0x80000010 (PA_GENERIC_ERROR).
- The vendor kernel uses ufs_qcom_assert_reset() (read-modify-write on CFG1
  BIT(1)) which PRESERVES BIT(26) from the bootloader. Mainline's GCC core
  reset clears it. Neither vendor nor mainline explicitly enables it before
  link startup — vendor doesn't need to because it never loses it.

Fix: restore BIT(26) in power_up_sequence() after select_unipro_mode(), so
the device M-PHY has a valid reference clock when it comes out of GPIO reset.

Also adds REG_UFS_CFG1 to PRE-LINK diagnostic for confirmation.
"""
import sys

path = '/opt/hiveos/build/cepheus/build/linux-4a8d88483/drivers/ufs/host/ufs-qcom.c'
with open(path) as f:
    text = f.read()

# Patch 1: restore device ref clock in power_up_sequence() after core reset
old_pup = (
    '\tufs_qcom_select_unipro_mode(host);\n'
    '\n'
    '\treturn 0;\n'
    '\n'
    'out_disable_phy:\n'
    '\tphy_exit(phy);\n'
)

new_pup = (
    '\tufs_qcom_select_unipro_mode(host);\n'
    '\n'
    '\t/*\n'
    '\t * ufs_qcom_host_reset() (GCC peripheral reset) clears REG_UFS_CFG1\n'
    '\t * BIT(26) to its hardware default (0). BIT(26) enables the reference\n'
    '\t * clock output to the UFS device M-PHY. Without it the device M-PHY\n'
    '\t * cannot lock its PLL or complete T_TxActivate → PA_GENERIC_ERROR.\n'
    '\t * Vendor preserves BIT(26) via read-modify-write PHY soft-reset; we\n'
    '\t * must restore it explicitly after the core reset clears it.\n'
    '\t */\n'
    '\tufshcd_rmwl(hba, BIT(26), BIT(26), REG_UFS_CFG1);\n'
    '\n'
    '\treturn 0;\n'
    '\n'
    'out_disable_phy:\n'
    '\tphy_exit(phy);\n'
)

if old_pup not in text:
    print('ERROR: power_up_sequence() target block not found')
    sys.exit(1)

text = text.replace(old_pup, new_pup, 1)

# Patch 2: add REG_UFS_CFG1 to PRE-LINK diagnostic
old_diag = (
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
)

new_diag = (
    '\t\t\tu32 tx_fsm = 0, uecpa = 0, cfg0, cfg1, hw_ver, dme_clk = 0;\n'
    '\t\t\tufshcd_dme_get(hba, UIC_ARG_MIB_SEL(MPHY_TX_FSM_STATE,\n'
    '\t\t\t\tUIC_ARG_MPHY_TX_GEN_SEL_INDEX(0)), &tx_fsm);\n'
    '\t\t\tufshcd_dme_get(hba, UIC_ARG_MIB(DME_VS_CORE_CLK_CTRL), &dme_clk);\n'
    '\t\t\tuecpa = ufshcd_readl(hba, REG_UIC_ERROR_CODE_PHY_ADAPTER_LAYER);\n'
    '\t\t\tcfg0 = ufshcd_readl(hba, REG_UFS_CFG0);\n'
    '\t\t\tcfg1 = ufshcd_readl(hba, REG_UFS_CFG1);\n'
    '\t\t\thw_ver = ufshcd_readl(hba, REG_UFS_HW_VERSION);\n'
    '\t\t\t/* Set to 3s (900M cycles @ 300MHz) to rule out timer-too-short */\n'
    '\t\t\tufshcd_writel(hba, 900000000U, REG_UFS_CFG0);\n'
    '\t\t\tdev_err(hba->dev,\n'
    '\t\t\t\t"PRE-LINK: TX_FSM=%u UECPA=0x%x IS=0x%x CFG0=0x%x CFG1=0x%x HW_VER=0x%x DME_CLK=0x%x\\n",\n'
    '\t\t\t\ttx_fsm, uecpa,\n'
    '\t\t\t\tufshcd_readl(hba, REG_INTERRUPT_STATUS),\n'
    '\t\t\t\tcfg0, cfg1, hw_ver, dme_clk);\n'
)

if old_diag not in text:
    print('ERROR: PRE-LINK diagnostic block not found')
    sys.exit(1)

text = text.replace(old_diag, new_diag, 1)

with open(path, 'w') as f:
    f.write(text)
print('power_up_sequence(): device ref clock (CFG1 BIT(26)) enabled after core reset OK')
print('PRE-LINK diagnostic: CFG1 readout added OK')
