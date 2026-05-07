#!/usr/bin/env python3
"""
Apply SM8150-specific (hw_ver 4.1.0, "v2") QMP UFS PHY calibration overrides
that are missing from the mainline sm8150_ufsphy_tx[] and sm8150_ufsphy_rx[] tables.

Root cause of TX_FSM stuck in SLEEP / PA_GENERIC_ERROR:
  Mainline copied the base (hw_ver 4.0.0) calibration values.
  The vendor driver's calibrate_phy() applies a second table,
  phy_cal_table_rate_A_v2_g3[], that overrides several registers for
  hw_ver 4.1.0 (SM8150 production = "v2").  The most critical:

    QSERDES_TX0_LANE_MODE_1: 0x05 → 0x35
      Bits 5:4 (0x30) enable additional TX lane features required for the
      TX to complete its SLEEP→BURST activation on SM8150.  Without them
      the TX activates to SLEEP but never reaches BURST → T_TxActivate
      timeout → UECPA=0x80000010 (PA_GENERIC_ERROR).

The RX overrides improve signal detection / eye quality but may not block
link startup; fixing LANE_MODE_1 alone is the primary fix.

Vendor source: phy-qcom-ufs-qmp-v4.h  phy_cal_table_rate_A_v2_g3[]
  QSERDES_TX0_LANE_MODE_1                    0x35  (was 0x05)
  QSERDES_RX0_UCDR_SO_SATURATION_AND_ENABLE  0x5A  (was 0x4B)
  QSERDES_RX0_UCDR_FO_GAIN                   0x0E  (was 0x0C)
  QSERDES_RX0_RX_MODE_00_LOW                 0x6D  (was 0x36)
  QSERDES_RX0_RX_MODE_00_HIGH                0x6D  (was 0x36)
  QSERDES_RX0_RX_MODE_00_HIGH2               0xED  (was 0xF6)
  QSERDES_RX0_RX_MODE_00_HIGH4               0x3C  (was 0x3D)
"""
import sys

path = '/opt/nerveos/build/cepheus/build/linux-4a8d88483/drivers/phy/qualcomm/phy-qcom-qmp-ufs.c'
with open(path) as f:
    text = f.read()

errors = []

# Patch 1: TX LANE_MODE_1 — the primary fix for TX-stuck-in-SLEEP
old = '\tQMP_PHY_INIT_CFG(QSERDES_V4_TX_LANE_MODE_1, 0x05),\n'
new = '\tQMP_PHY_INIT_CFG(QSERDES_V4_TX_LANE_MODE_1, 0x35),\n'
if old not in text:
    errors.append('TX_LANE_MODE_1 0x05 not found')
else:
    text = text.replace(old, new, 1)
    print('TX_LANE_MODE_1: 0x05 → 0x35 OK')

# Patch 2: RX UCDR_SO_SATURATION_AND_ENABLE
old = '\tQMP_PHY_INIT_CFG(QSERDES_V4_RX_UCDR_SO_SATURATION_AND_ENABLE, 0x4b),\n'
new = '\tQMP_PHY_INIT_CFG(QSERDES_V4_RX_UCDR_SO_SATURATION_AND_ENABLE, 0x5a),\n'
if old not in text:
    errors.append('RX_UCDR_SO_SATURATION 0x4b not found in base table')
else:
    text = text.replace(old, new, 1)
    print('RX_UCDR_SO_SATURATION_AND_ENABLE: 0x4b → 0x5a OK')

# Patch 3: RX UCDR_FO_GAIN (first occurrence = base table, not g4 override)
old = '\tQMP_PHY_INIT_CFG(QSERDES_V4_RX_UCDR_FO_GAIN, 0x0c),\n'
new = '\tQMP_PHY_INIT_CFG(QSERDES_V4_RX_UCDR_FO_GAIN, 0x0e),\n'
if old not in text:
    errors.append('RX_UCDR_FO_GAIN 0x0c not found in base table')
else:
    text = text.replace(old, new, 1)
    print('RX_UCDR_FO_GAIN: 0x0c → 0x0e OK')

# Patch 4: RX_MODE_00_LOW
old = '\tQMP_PHY_INIT_CFG(QSERDES_V4_RX_RX_MODE_00_LOW, 0x36),\n'
new = '\tQMP_PHY_INIT_CFG(QSERDES_V4_RX_RX_MODE_00_LOW, 0x6d),\n'
if old not in text:
    errors.append('RX_MODE_00_LOW 0x36 not found')
else:
    text = text.replace(old, new, 1)
    print('RX_MODE_00_LOW: 0x36 → 0x6d OK')

# Patch 5: RX_MODE_00_HIGH
old = '\tQMP_PHY_INIT_CFG(QSERDES_V4_RX_RX_MODE_00_HIGH, 0x36),\n'
new = '\tQMP_PHY_INIT_CFG(QSERDES_V4_RX_RX_MODE_00_HIGH, 0x6d),\n'
if old not in text:
    errors.append('RX_MODE_00_HIGH 0x36 not found')
else:
    text = text.replace(old, new, 1)
    print('RX_MODE_00_HIGH: 0x36 → 0x6d OK')

# Patch 6: RX_MODE_00_HIGH2
old = '\tQMP_PHY_INIT_CFG(QSERDES_V4_RX_RX_MODE_00_HIGH2, 0xf6),\n'
new = '\tQMP_PHY_INIT_CFG(QSERDES_V4_RX_RX_MODE_00_HIGH2, 0xed),\n'
if old not in text:
    errors.append('RX_MODE_00_HIGH2 0xf6 not found')
else:
    text = text.replace(old, new, 1)
    print('RX_MODE_00_HIGH2: 0xf6 → 0xed OK')

# Patch 7: RX_MODE_00_HIGH4 (in the base table, 0x3d; g4 table has 0x6c which stays)
old = '\tQMP_PHY_INIT_CFG(QSERDES_V4_RX_RX_MODE_00_HIGH4, 0x3d),\n'
new = '\tQMP_PHY_INIT_CFG(QSERDES_V4_RX_RX_MODE_00_HIGH4, 0x3c),\n'
if old not in text:
    errors.append('RX_MODE_00_HIGH4 0x3d not found in base table')
else:
    text = text.replace(old, new, 1)
    print('RX_MODE_00_HIGH4: 0x3d → 0x3c OK')

if errors:
    for e in errors:
        print(f'ERROR: {e}')
    sys.exit(1)

with open(path, 'w') as f:
    f.write(text)
print('All SM8150 v2 PHY calibration overrides applied.')
