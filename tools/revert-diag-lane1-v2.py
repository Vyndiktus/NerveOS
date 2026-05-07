#!/usr/bin/env python3
"""Revert lane 1 TX_FSM diagnostic - DME_GET for lane 1 hangs on single-lane PHY."""

path = '/opt/nerveos/build/cepheus/build/linux-4a8d88483/drivers/ufs/host/ufs-qcom.c'
with open(path, 'rb') as f:
    data = f.read()

# 1. Remove lane 1 dme_get line
r1_old = (b'\t\t\tufshcd_dme_get(hba, UIC_ARG_MIB_SEL(MPHY_TX_FSM_STATE,\n'
          b'\t\t\t\tUIC_ARG_MPHY_TX_GEN_SEL_INDEX(1)), &tx_fsm1);\n')
if r1_old in data:
    data = data.replace(r1_old, b'', 1)
    print('Lane 1 dme_get removed')
else:
    print('WARNING: lane 1 dme_get not found')

# 2. Fix declarations
r2_old = b'u32 tx_fsm0 = 0xff, tx_fsm1 = 0xff, uecpa;'
r2_new = b'u32 tx_fsm = 0, uecpa = 0;'
if r2_old in data:
    data = data.replace(r2_old, r2_new, 1)
    print('Declarations fixed')

# 3. Fix dme_get arg &tx_fsm0 -> &tx_fsm
r3_old = b'UIC_ARG_MPHY_TX_GEN_SEL_INDEX(0)), &tx_fsm0);'
r3_new = b'UIC_ARG_MPHY_TX_GEN_SEL_INDEX(0)), &tx_fsm);'
if r3_old in data:
    data = data.replace(r3_old, r3_new, 1)
    print('dme_get arg fixed')

# 4. Fix dev_err - split into two replacements
# 4a: fix the format string line
r4_old = b'"PRE-LINK: TX_FSM0=%u TX_FSM1=%u UECPA=0x%x IS=0x%x'
r4_new = b'"PRE-LINK: TX_FSM=%u UECPA=0x%x IS=0x%x'
if r4_old in data:
    data = data.replace(r4_old, r4_new, 1)
    print('format string fixed')

# 4b: fix the args tx_fsm0, tx_fsm1, uecpa -> tx_fsm, uecpa
r5_old = b'\t\t\t\ttx_fsm0, tx_fsm1, uecpa,'
r5_new = b'\t\t\t\ttx_fsm, uecpa,'
if r5_old in data:
    data = data.replace(r5_old, r5_new, 1)
    print('args fixed')

# 4c: fix dev_err split format (dev_err(hba->dev,\n\t\t\t\t"... -> dev_err(hba->dev, "...)
r6_old = b'dev_err(hba->dev,\n\t\t\t\t"PRE-LINK:'
r6_new = b'dev_err(hba->dev, "PRE-LINK:'
if r6_old in data:
    data = data.replace(r6_old, r6_new, 1)
    print('dev_err format fixed')

with open(path, 'wb') as f:
    f.write(data)
print('Done')

# Verify
with open(path, 'rb') as f:
    d = f.read()
idx = d.find(b'PRE-LINK:')
print('Result context:', repr(d[idx-50:idx+80]))
