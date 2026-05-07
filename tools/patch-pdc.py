#!/usr/bin/env python3
"""
Fix: include UFS_PHY_POWER_DOWN_CONTROL = 0x01 in sm8150_ufsphy_pcs[] init table.

Root cause:
  qmp_ufs_com_init() sets POWER_DOWN_CONTROL (PCS+0x004, SW_PWRDN BIT(0)) to 0x01
  (PHY powered up) before qmp_ufs_power_on() runs. But qmp_ufs_power_on() then asserts
  PCS SW_RESET (BIT(0) at PCS+0x008), which resets all PCS registers — including
  POWER_DOWN_CONTROL — back to the hardware reset value of 0 (PHY powered down).

  The init tables written during SW_RESET assertion do not include POWER_DOWN_CONTROL,
  so after SW_RESET deassertion the PHY analog remains powered down. SerDes is then
  started (PHY_START BIT(0) set) against a powered-down PHY → TX cannot complete
  T_TxActivate → UECPA=0x80000010 (PA_GENERIC_ERROR).

  Vendor phy_cal_table_rate_A[] entry 0: UFS_PHY_POWER_DOWN_CONTROL = 0x01, written
  while SW_RESET is asserted so it is retained when SW_RESET is deasserted.
  Mainline omits this register from sm8150_ufsphy_pcs[] entirely.

Fix: add as the first entry so it is written during qmp_ufs_init_registers()
(while SW_RESET is asserted) and retained after deassertion.
"""
import sys

path = '/opt/nerveos/build/cepheus/build/linux-4a8d88483/drivers/phy/qualcomm/phy-qcom-qmp-ufs.c'
with open(path) as f:
    text = f.read()

old = (
    'static const struct qmp_phy_init_tbl sm8150_ufsphy_pcs[] = {\n'
    '\tQMP_PHY_INIT_CFG(QPHY_V4_PCS_UFS_TIMER_20US_CORECLK_STEPS_MSB, 0x16),\n'
)
new = (
    'static const struct qmp_phy_init_tbl sm8150_ufsphy_pcs[] = {\n'
    '\t/*\n'
    '\t * SW_RESET (PCS+0x008) assertion clears POWER_DOWN_CONTROL (PCS+0x004)\n'
    '\t * to its hardware reset value (0 = powered down). Write 0x01 here so it\n'
    '\t * is restored before SW_RESET is deasserted and SerDes starts.\n'
    '\t * Matches vendor phy_cal_table_rate_A[] entry 0: POWER_DOWN_CONTROL=0x01.\n'
    '\t */\n'
    '\tQMP_PHY_INIT_CFG(QPHY_V4_PCS_UFS_POWER_DOWN_CONTROL, 0x01),\n'
    '\tQMP_PHY_INIT_CFG(QPHY_V4_PCS_UFS_TIMER_20US_CORECLK_STEPS_MSB, 0x16),\n'
)

if old not in text:
    print('ERROR: sm8150_ufsphy_pcs[] header not found (may already be patched)')
    sys.exit(1)

text = text.replace(old, new, 1)
print('POWER_DOWN_CONTROL 0x01: added as first entry in sm8150_ufsphy_pcs[] OK')

with open(path, 'w') as f:
    f.write(text)
print('SM8150 PHY POWER_DOWN_CONTROL fix applied.')
