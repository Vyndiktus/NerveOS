#!/usr/bin/env python3
"""
Two changes to fix SM8150 UFS link startup:
1. Remove ufs_qcom_enable_hw_clk_gating from POST_CHANGE (called too early,
   before link startup - may gate clock needed for M-PHY TX activation).
2. Set PA_TActivate=10 before link startup (Qualcomm vendor kernel does this).
"""

path = '/opt/nerveos/build/cepheus/build/linux-4a8d88483/drivers/ufs/host/ufs-qcom.c'
with open(path, 'rb') as f:
    data = f.read()

# Change 1: Remove ufs_qcom_enable_hw_clk_gating from POST_CHANGE
# It should be called after link startup, not before.
old_cgc = (
    b'\t\t/* check if UFS PHY moved from DISABLED to HIBERN8 */\n'
    b'\t\terr = ufs_qcom_check_hibern8(hba);\n'
    b'\t\tufs_qcom_enable_hw_clk_gating(hba);\n'
    b'\t\tufs_qcom_ice_enable(host);\n'
)
new_cgc = (
    b'\t\t/* check if UFS PHY moved from DISABLED to HIBERN8 */\n'
    b'\t\terr = ufs_qcom_check_hibern8(hba);\n'
    b'\t\t/* Note: hw_clk_gating deferred to after link startup */\n'
    b'\t\tufs_qcom_ice_enable(host);\n'
)

if old_cgc not in data:
    print('ERROR: POST_CHANGE CGC block not found')
    import sys; sys.exit(1)
data = data.replace(old_cgc, new_cgc, 1)
print('Change 1: removed hw_clk_gating from POST_CHANGE')

# Change 2: Add PA_TActivate=10 in link_startup_notify PRE_CHANGE,
# before the PRE-LINK diagnostic. Vendor kernel sets this before link startup.
old_lsc = (
    b'\t\tmsleep(150);\n'
    b'\n'
    b'\t\t/* PRE-LINK diagnostic: log TX_FSM and PHY state (HCE done, UIC ready) */\n'
)
new_lsc = (
    b'\t\t/*\n'
    b'\t\t * Set PA_TActivate per Qualcomm vendor kernel requirement.\n'
    b'\t\t * Without this, T_TxActivate timer may expire during link startup.\n'
    b'\t\t */\n'
    b'\t\tufshcd_dme_set(hba, UIC_ARG_MIB(PA_TACTIVATE), 10);\n'
    b'\n'
    b'\t\t/* PRE-LINK diagnostic: log TX_FSM and PHY state (HCE done, UIC ready) */\n'
)

if old_lsc not in data:
    print('ERROR: msleep block not found')
    idx = data.find(b'msleep(150)')
    if idx >= 0:
        print(repr(data[idx-50:idx+200]))
    import sys; sys.exit(1)
data = data.replace(old_lsc, new_lsc, 1)
print('Change 2: PA_TActivate=10 added before link startup')

with open(path, 'wb') as f:
    f.write(data)

print('Done')
print('CGC removed from POST_CHANGE:', b'hw_clk_gating deferred' in data)
print('PA_TActivate set:', b'PA_TACTIVATE), 10' in data)
