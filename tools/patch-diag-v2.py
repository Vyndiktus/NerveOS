#!/usr/bin/env python3
"""
Diagnostic + fix patches for SM8150 UFS link startup debugging.
Changes:
  1. PHY_INIT_COMPLETE_TIMEOUT: 10000 → 1000000 (match vendor 1s wait)
  2. qmp_ufs_calibrate(): add readback of TIMER_20US registers
  3. ufs-qcom.c: PA_TACTIVATE 10 → 0x7F (more margin)
  4. ufshcd.c: add TX_FSM readback in POST-LINK-FAIL (key diagnosis)
"""

import sys

BASE = '/opt/hiveos/build/cepheus/build/linux-4a8d88483'

# ── 1. PHY_INIT_COMPLETE_TIMEOUT ──────────────────────────────────────────────
phy_path = f'{BASE}/drivers/phy/qualcomm/phy-qcom-qmp-ufs.c'
with open(phy_path, 'r') as f:
    text = f.read()

old = '#define PHY_INIT_COMPLETE_TIMEOUT\t\t10000'
new = '#define PHY_INIT_COMPLETE_TIMEOUT\t\t1000000'
if old not in text:
    print('ERROR: PHY_INIT_COMPLETE_TIMEOUT not found as expected')
    sys.exit(1)
text = text.replace(old, new, 1)

# ── 2. qmp_ufs_calibrate(): add readback ─────────────────────────────────────
old_cal = (
    '\t/* Vendor phy_cal_table_rate_A_g3[]: 20us M-PHY timer. 5848 cycles @ 300MHz. */\n'
    '\twritel(0x16, qmp->pcs + QPHY_V4_PCS_UFS_TIMER_20US_CORECLK_STEPS_MSB);\n'
    '\twritel(0xd8, qmp->pcs + QPHY_V4_PCS_UFS_TIMER_20US_CORECLK_STEPS_LSB);\n'
    '\treturn 0;\n'
    '}'
)
new_cal = (
    '\t/* Vendor phy_cal_table_rate_A_g3[]: 20us M-PHY timer. 5848 cycles @ 300MHz. */\n'
    '\twritel(0x16, qmp->pcs + QPHY_V4_PCS_UFS_TIMER_20US_CORECLK_STEPS_MSB);\n'
    '\twritel(0xd8, qmp->pcs + QPHY_V4_PCS_UFS_TIMER_20US_CORECLK_STEPS_LSB);\n'
    '\t/* Verify writes took effect */\n'
    '\t{\n'
    '\t\tu32 msb = readl(qmp->pcs + QPHY_V4_PCS_UFS_TIMER_20US_CORECLK_STEPS_MSB);\n'
    '\t\tu32 lsb = readl(qmp->pcs + QPHY_V4_PCS_UFS_TIMER_20US_CORECLK_STEPS_LSB);\n'
    '\t\tdev_err(qmp->dev, "TIMER_20US readback: MSB=0x%02x LSB=0x%02x (expect 0x16 0xd8)\\n", msb, lsb);\n'
    '\t}\n'
    '\treturn 0;\n'
    '}'
)
if old_cal not in text:
    print('ERROR: calibrate TIMER_20US block not found')
    sys.exit(1)
text = text.replace(old_cal, new_cal, 1)

with open(phy_path, 'w') as f:
    f.write(text)
print('phy-qcom-qmp-ufs.c: PHY_INIT_COMPLETE_TIMEOUT=1000000, TIMER_20US readback added')

# ── 3. ufs-qcom.c: PA_TACTIVATE 10 → 0x7F ───────────────────────────────────
ufsqcom_path = f'{BASE}/drivers/ufs/host/ufs-qcom.c'
with open(ufsqcom_path, 'r') as f:
    text = f.read()

old_ta = '\t\tufshcd_dme_set(hba, UIC_ARG_MIB(PA_TACTIVATE), 10);'
new_ta = '\t\tufshcd_dme_set(hba, UIC_ARG_MIB(PA_TACTIVATE), 0x7F);'
if old_ta not in text:
    print('ERROR: PA_TACTIVATE=10 not found in ufs-qcom.c')
    sys.exit(1)
text = text.replace(old_ta, new_ta, 1)

with open(ufsqcom_path, 'w') as f:
    f.write(text)
print('ufs-qcom.c: PA_TACTIVATE 10 → 0x7F')

# ── 4. ufshcd.c: TX_FSM readback in POST-LINK-FAIL ───────────────────────────
ufshcd_path = f'{BASE}/drivers/ufs/core/ufshcd.c'
with open(ufshcd_path, 'r') as f:
    text = f.read()

old_fail = (
    '\tif (ret)\n'
    '\t\tdev_err(hba->dev,\n'
    '\t\t\t"POST-LINK-FAIL: ret=%d IS=0x%x UECPA=0x%x UECDL=0x%x HCS=0x%x\\n",\n'
    '\t\t\tret,\n'
    '\t\t\tufshcd_readl(hba, REG_INTERRUPT_STATUS),\n'
    '\t\t\tufshcd_readl(hba, REG_UIC_ERROR_CODE_PHY_ADAPTER_LAYER),\n'
    '\t\t\tufshcd_readl(hba, REG_UIC_ERROR_CODE_DATA_LINK_LAYER),\n'
    '\t\t\tufshcd_readl(hba, REG_CONTROLLER_STATUS));\n'
    '\treturn ret;'
)
new_fail = (
    '\tif (ret) {\n'
    '\t\tu32 tx_fsm = 0;\n'
    '\t\tufshcd_dme_get(hba, UIC_ARG_MIB_SEL(MPHY_TX_FSM_STATE,\n'
    '\t\t\tUIC_ARG_MPHY_TX_GEN_SEL_INDEX(0)), &tx_fsm);\n'
    '\t\tdev_err(hba->dev,\n'
    '\t\t\t"POST-LINK-FAIL: ret=%d IS=0x%x UECPA=0x%x UECDL=0x%x HCS=0x%x TX_FSM=%u\\n",\n'
    '\t\t\tret,\n'
    '\t\t\tufshcd_readl(hba, REG_INTERRUPT_STATUS),\n'
    '\t\t\tufshcd_readl(hba, REG_UIC_ERROR_CODE_PHY_ADAPTER_LAYER),\n'
    '\t\t\tufshcd_readl(hba, REG_UIC_ERROR_CODE_DATA_LINK_LAYER),\n'
    '\t\t\tufshcd_readl(hba, REG_CONTROLLER_STATUS),\n'
    '\t\t\ttx_fsm);\n'
    '\t}\n'
    '\treturn ret;'
)
if old_fail not in text:
    print('ERROR: POST-LINK-FAIL block not found in ufshcd.c')
    sys.exit(1)
text = text.replace(old_fail, new_fail, 1)

with open(ufshcd_path, 'w') as f:
    f.write(text)
print('ufshcd.c: TX_FSM added to POST-LINK-FAIL')
print('All patches applied.')
