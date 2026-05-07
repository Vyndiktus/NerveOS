#!/usr/bin/env python3
"""
Add host controller PHY soft reset assert-before-init to qmp_ufs_power_on().
Matches vendor ufs_qcom_power_up_sequence(): assert -> calibrate -> deassert -> start SerDes.
Without this, CFG1.UFS_PHY_SOFT_RESET is never asserted, so the analog SerDes
starts from bootloader state and TIMER_20US writes may not be seen at the right time.
"""
import sys

path = '/opt/nerveos/build/cepheus/build/linux-4a8d88483/drivers/phy/qualcomm/phy-qcom-qmp-ufs.c'
with open(path) as f:
    text = f.read()

old = (
    '\tqmp_ufs_init_registers(qmp, cfg);\n'
    '\n'
    '\tret = reset_control_deassert(qmp->ufs_reset);\n'
    '\tif (ret)\n'
    '\t\treturn ret;\n'
    '\n'
    '\t/* Pull PHY out of reset state */\n'
    '\tif (!cfg->no_pcs_sw_reset)\n'
    '\t\tqphy_clrbits(pcs, cfg->regs[QPHY_SW_RESET], SW_RESET);\n'
    '\n'
    '\t/* start SerDes */\n'
    '\tqphy_setbits(pcs, cfg->regs[QPHY_START_CTRL], SERDES_START);'
)

new = (
    '\t/*\n'
    '\t * Assert host controller PHY soft reset (REG_UFS_CFG1.UFS_PHY_SOFT_RESET)\n'
    '\t * to put analog SerDes in a known clean state before writing init tables.\n'
    '\t * Matches vendor ufs_qcom_assert_reset() + 1ms delay in power_up_sequence().\n'
    '\t */\n'
    '\treset_control_assert(qmp->ufs_reset);\n'
    '\tusleep_range(1000, 1100);\n'
    '\n'
    '\t/* Write all init tables (including TIMER_20US) with reset asserted.\n'
    '\t * PCS registers retain values across reset deassertion. */\n'
    '\tqmp_ufs_init_registers(qmp, cfg);\n'
    '\n'
    '\t/* Deassert host PHY soft reset + 1ms settle.\n'
    '\t * Matches vendor ufs_qcom_deassert_reset() + 1ms delay. */\n'
    '\tret = reset_control_deassert(qmp->ufs_reset);\n'
    '\tif (ret)\n'
    '\t\treturn ret;\n'
    '\tusleep_range(1000, 1100);\n'
    '\n'
    '\t/* Pull PHY out of reset state */\n'
    '\tif (!cfg->no_pcs_sw_reset)\n'
    '\t\tqphy_clrbits(pcs, cfg->regs[QPHY_SW_RESET], SW_RESET);\n'
    '\n'
    '\t/* start SerDes */\n'
    '\tqphy_setbits(pcs, cfg->regs[QPHY_START_CTRL], SERDES_START);'
)

if old not in text:
    print('ERROR: target block not found in qmp_ufs_power_on()')
    sys.exit(1)

text = text.replace(old, new, 1)
with open(path, 'w') as f:
    f.write(text)
print('qmp_ufs_power_on(): reset_control_assert added before init_registers OK')
