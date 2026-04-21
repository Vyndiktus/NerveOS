#!/usr/bin/env python3
"""
Add PCS SW_RESET assert before qmp_ufs_init_registers() in qmp_ufs_power_on().

Root cause of T_TxActivate failure on SM8150:
- qmp->ufs_reset is NULL for SM8150 (no_pcs_sw_reset=false).
  reset_control_assert/deassert on NULL is a no-op in the kernel.
  So patch-phy-reset-cycle.py only added delays but no actual reset.

- Vendor phy-qcom-ufs-qmp-v4.c::calibrate_phy() explicitly writes:
    writel(0x01, mmio + UFS_PHY_SW_RESET)  <- assert PCS SW_RESET
    wmb();
    [write all init tables]
    writel(0x00, mmio + UFS_PHY_SW_RESET)  <- deassert PCS SW_RESET
  This ensures PCS registers are in a known reset state when tables
  are written. Mainline never asserts SW_RESET before init.

- The existing qphy_clrbits(QPHY_SW_RESET) at the end already deasserts.
  We just need to assert it first.
"""
import sys

path = '/opt/hiveos/build/cepheus/build/linux-4a8d88483/drivers/phy/qualcomm/phy-qcom-qmp-ufs.c'
with open(path) as f:
    text = f.read()

old = (
    '\t/* Write all init tables (including TIMER_20US) with reset asserted.\n'
    '\t * PCS registers retain values across reset deassertion. */\n'
    '\tqmp_ufs_init_registers(qmp, cfg);\n'
)

new = (
    '\t/*\n'
    '\t * Vendor phy-qcom-ufs-qmp-v4.c::calibrate_phy() asserts PCS SW_RESET\n'
    '\t * (writel(0x01, mmio+UFS_PHY_SW_RESET)) before writing init tables so\n'
    '\t * PCS registers start from a clean reset state. qmp->ufs_reset is NULL\n'
    '\t * for SM8150 (no_pcs_sw_reset=false) so reset_control_assert above is\n'
    '\t * a no-op; we must assert SW_RESET via the PCS register directly.\n'
    '\t */\n'
    '\tif (!cfg->no_pcs_sw_reset)\n'
    '\t\tqphy_setbits(pcs, cfg->regs[QPHY_SW_RESET], SW_RESET);\n'
    '\n'
    '\t/* Write all init tables (including TIMER_20US) with SW_RESET asserted.\n'
    '\t * PCS registers retain values across SW_RESET deassertion. */\n'
    '\tqmp_ufs_init_registers(qmp, cfg);\n'
)

if old not in text:
    print('ERROR: target block not found — check current patch state')
    sys.exit(1)

text = text.replace(old, new, 1)
with open(path, 'w') as f:
    f.write(text)
print('qmp_ufs_power_on(): PCS SW_RESET assert added before init_registers OK')
