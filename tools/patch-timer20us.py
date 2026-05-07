#!/usr/bin/env python3
"""
Fix SM8150 UFS link startup: add TIMER_20US_CORECLK_STEPS PHY registers.

The vendor phy_cal_table_rate_A_g3[] writes two PHY PCS timing registers:
  TIMER_20US_CORECLK_STEPS_MSB (pcs+0x00C) = 0x16
  TIMER_20US_CORECLK_STEPS_LSB (pcs+0x010) = 0xD8
  Combined: 0x16D8 = 5848 core clock cycles per 20us (~292 MHz core clock)

These configure the M-PHY internal 20us reference timer used for state machine
transitions (SLEEP->STALL->BURST). With the default value of 0 after BCR reset,
the timer never fires, the TX M-PHY state machine stalls, and T_TxActivate
expires -> UECPA=0x80000010 (PA_PHY_GENERIC_ERROR).

mainline ufs_qcom_cfg_timers() only writes REG_UFS_SYS1CLK_1US (host controller),
NOT the PHY PCS TIMER_20US registers. These must be in the PHY init table.
"""

import sys

phy_path = '/opt/nerveos/build/cepheus/build/linux-4a8d88483/drivers/phy/qualcomm/phy-qcom-qmp-ufs.c'
with open(phy_path, 'r') as f:
    text = f.read()

old = (
    'static const struct qmp_phy_init_tbl sm8150_ufsphy_pcs[] = {\n'
    '\tQMP_PHY_INIT_CFG(QPHY_V4_PCS_UFS_RX_SIGDET_CTRL2, 0x6d),\n'
    '\tQMP_PHY_INIT_CFG(QPHY_V4_PCS_UFS_TX_LARGE_AMP_DRV_LVL, 0x0a),\n'
    '\tQMP_PHY_INIT_CFG(QPHY_V4_PCS_UFS_TX_SMALL_AMP_DRV_LVL, 0x02),\n'
    '\tQMP_PHY_INIT_CFG(QPHY_V4_PCS_UFS_PLL_CNTL, 0x03),\n'
    '\tQMP_PHY_INIT_CFG(QPHY_V4_PCS_UFS_TX_HSGEAR_CAPABILITY, 0x03),\n'
    '\tQMP_PHY_INIT_CFG(QPHY_V4_PCS_UFS_RX_HSGEAR_CAPABILITY, 0x03),\n'
    '\tQMP_PHY_INIT_CFG(QPHY_V4_PCS_UFS_TX_MID_TERM_CTRL1, 0x43),\n'
    '\tQMP_PHY_INIT_CFG(QPHY_V4_PCS_UFS_DEBUG_BUS_CLKSEL, 0x1f),\n'
    '\tQMP_PHY_INIT_CFG(QPHY_V4_PCS_UFS_TX_PWM_GEAR_BAND, 0xaa),\n'
    '\tQMP_PHY_INIT_CFG(QPHY_V4_PCS_UFS_TX_HS_GEAR_BAND, 0x06),\n'
    '\tQMP_PHY_INIT_CFG(QPHY_V4_PCS_UFS_RX_MIN_HIBERN8_TIME, 0xff),\n'
    '\tQMP_PHY_INIT_CFG(QPHY_V4_PCS_UFS_MULTI_LANE_CTRL1, 0x02),\n'
    '};'
)

new = (
    'static const struct qmp_phy_init_tbl sm8150_ufsphy_pcs[] = {\n'
    '\tQMP_PHY_INIT_CFG(QPHY_V4_PCS_UFS_TIMER_20US_CORECLK_STEPS_MSB, 0x16),\n'
    '\tQMP_PHY_INIT_CFG(QPHY_V4_PCS_UFS_TIMER_20US_CORECLK_STEPS_LSB, 0xd8),\n'
    '\tQMP_PHY_INIT_CFG(QPHY_V4_PCS_UFS_RX_SIGDET_CTRL2, 0x6d),\n'
    '\tQMP_PHY_INIT_CFG(QPHY_V4_PCS_UFS_TX_LARGE_AMP_DRV_LVL, 0x0a),\n'
    '\tQMP_PHY_INIT_CFG(QPHY_V4_PCS_UFS_TX_SMALL_AMP_DRV_LVL, 0x02),\n'
    '\tQMP_PHY_INIT_CFG(QPHY_V4_PCS_UFS_PLL_CNTL, 0x03),\n'
    '\tQMP_PHY_INIT_CFG(QPHY_V4_PCS_UFS_TX_HSGEAR_CAPABILITY, 0x03),\n'
    '\tQMP_PHY_INIT_CFG(QPHY_V4_PCS_UFS_RX_HSGEAR_CAPABILITY, 0x03),\n'
    '\tQMP_PHY_INIT_CFG(QPHY_V4_PCS_UFS_TX_MID_TERM_CTRL1, 0x43),\n'
    '\tQMP_PHY_INIT_CFG(QPHY_V4_PCS_UFS_DEBUG_BUS_CLKSEL, 0x1f),\n'
    '\tQMP_PHY_INIT_CFG(QPHY_V4_PCS_UFS_TX_PWM_GEAR_BAND, 0xaa),\n'
    '\tQMP_PHY_INIT_CFG(QPHY_V4_PCS_UFS_TX_HS_GEAR_BAND, 0x06),\n'
    '\tQMP_PHY_INIT_CFG(QPHY_V4_PCS_UFS_RX_MIN_HIBERN8_TIME, 0xff),\n'
    '\tQMP_PHY_INIT_CFG(QPHY_V4_PCS_UFS_MULTI_LANE_CTRL1, 0x02),\n'
    '};'
)

if old not in text:
    print('ERROR: sm8150_ufsphy_pcs table not found as expected')
    idx = text.find('sm8150_ufsphy_pcs')
    if idx >= 0:
        print(repr(text[idx:idx+800]))
    sys.exit(1)

text = text.replace(old, new, 1)
with open(phy_path, 'w') as f:
    f.write(text)

print('TIMER_20US registers added to sm8150_ufsphy_pcs[] OK')
print('MSB present:', 'TIMER_20US_CORECLK_STEPS_MSB, 0x16' in text)
print('LSB present:', 'TIMER_20US_CORECLK_STEPS_LSB, 0xd8' in text)
