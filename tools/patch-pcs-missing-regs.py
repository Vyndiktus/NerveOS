#!/usr/bin/env python3
"""
Fix SM8150 UFS link startup: add missing PCS registers to sm8150_ufsphy_pcs[].

The mainline sm8150_ufsphy_pcs[] init table is missing 5 registers that the
vendor phy-qcom-ufs-qmp-v4.c writes during calibration:

  TX_PWM_GEAR_BAND  (pcs+0x160) = 0xAA  -- clock band for PWM gears 1-4
  TX_HS_GEAR_BAND   (pcs+0x168) = 0x06  -- clock band for HS gears
  TX_HSGEAR_CAPABILITY (pcs+0x074) = 0x03  -- max HS gear advertised
  RX_HSGEAR_CAPABILITY (pcs+0x0B4) = 0x03  -- max HS gear advertised
  PLL_CNTL          (pcs+0x02C) = 0x03  -- PLL control bits

TX_PWM_GEAR_BAND = 0 (default after BCR reset) means no valid clock band is
selected for PWM mode, preventing the TX from generating a clock during link
startup. The TX M-PHY can't transition from SLEEP to STALL, causing T_TxActivate
timeout (UECPA=0x80000010 = PA_PHY_GENERIC_ERROR).

TIMER_20US registers are written by ufs_qcom_cfg_timers() so omitted here.
POWER_DOWN_CONTROL default after BCR reset is 0x01 (powered on).
"""

import sys

phy_path = '/opt/nerveos/build/cepheus/build/linux-4a8d88483/drivers/phy/qualcomm/phy-qcom-qmp-ufs.c'
with open(phy_path, 'r') as f:
    text = f.read()

# Add missing registers to sm8150_ufsphy_pcs[]
# Insert before RX_MIN_HIBERN8_TIME (near end of table) to keep ordering logical
old = (
    '\tstatic const struct qmp_phy_init_tbl sm8150_ufsphy_pcs[] = {\n'
    '\tQMP_PHY_INIT_CFG(QPHY_V4_PCS_UFS_RX_SIGDET_CTRL2, 0x6d),\n'
    '\tQMP_PHY_INIT_CFG(QPHY_V4_PCS_UFS_TX_LARGE_AMP_DRV_LVL, 0x0a),\n'
    '\tQMP_PHY_INIT_CFG(QPHY_V4_PCS_UFS_TX_SMALL_AMP_DRV_LVL, 0x02),\n'
    '\tQMP_PHY_INIT_CFG(QPHY_V4_PCS_UFS_TX_MID_TERM_CTRL1, 0x43),\n'
    '\tQMP_PHY_INIT_CFG(QPHY_V4_PCS_UFS_DEBUG_BUS_CLKSEL, 0x1f),\n'
    '\tQMP_PHY_INIT_CFG(QPHY_V4_PCS_UFS_RX_MIN_HIBERN8_TIME, 0xff),\n'
    '\tQMP_PHY_INIT_CFG(QPHY_V4_PCS_UFS_MULTI_LANE_CTRL1, 0x02),\n'
    '};'
)

new = (
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

if old not in text:
    print('ERROR: sm8150_ufsphy_pcs table not found as expected')
    idx = text.find('sm8150_ufsphy_pcs')
    if idx >= 0:
        print(repr(text[idx:idx+600]))
    sys.exit(1)

text = text.replace(old, new, 1)
with open(phy_path, 'w') as f:
    f.write(text)

print('Missing PCS registers added to sm8150_ufsphy_pcs[] OK')
print('TX_PWM_GEAR_BAND present:', 'TX_PWM_GEAR_BAND, 0xaa' in text)
print('TX_HS_GEAR_BAND present:', 'TX_HS_GEAR_BAND, 0x06' in text)
print('PLL_CNTL present:', 'PLL_CNTL, 0x03' in text)
