#!/usr/bin/env python3
"""
Move PRE-LINK diagnostic from hce_enable_notify(PRE_CHANGE) to
link_startup_notify(PRE_CHANGE). Running a DME_GET before HCE is complete
causes a 500ms timeout + late interrupt that may corrupt HCI state.
"""

path = '/opt/nerveos/build/cepheus/build/linux-4a8d88483/drivers/ufs/host/ufs-qcom.c'
with open(path, 'rb') as f:
    data = f.read()

# Remove PRE-LINK diagnostic from hce_enable_notify PRE_CHANGE
old_diag = (
    b'\n'
    b'\t\t/* Diagnostic: log TX_FSM_STATE and UECPA before DME_LINK_STARTUP */\n'
    b'\t\t{\n'
    b'\t\t\tu32 tx_fsm = 0, uecpa = 0;\n'
    b'\t\t\tufshcd_dme_get(hba, UIC_ARG_MIB_SEL(MPHY_TX_FSM_STATE,\n'
    b'\t\t\t\tUIC_ARG_MPHY_TX_GEN_SEL_INDEX(0)), &tx_fsm);\n'
    b'\t\t\tuecpa = ufshcd_readl(hba, REG_UIC_ERROR_CODE_PHY_ADAPTER_LAYER);\n'
    b'\t\t\tdev_err(hba->dev, "PRE-LINK: TX_FSM=%u UECPA=0x%x IS=0x%x\\n",\n'
    b'\t\t\t\ttx_fsm, uecpa,\n'
    b'\t\t\t\tufshcd_readl(hba, REG_INTERRUPT_STATUS));\n'
    b'\t\t}\n'
    b'\t\tbreak;\n'
    b'\t}\n'  # end of PRE_CHANGE case + close of switch — need surrounding context
)

# More targeted: just remove the diagnostic block itself
old_diag2 = (
    b'\n\t\t/* Diagnostic: log TX_FSM_STATE and UECPA before DME_LINK_STARTUP */\n'
    b'\t\t{\n'
    b'\t\t\tu32 tx_fsm = 0, uecpa = 0;\n'
    b'\t\t\tufshcd_dme_get(hba, UIC_ARG_MIB_SEL(MPHY_TX_FSM_STATE,\n'
    b'\t\t\t\tUIC_ARG_MPHY_TX_GEN_SEL_INDEX(0)), &tx_fsm);\n'
    b'\t\t\tuecpa = ufshcd_readl(hba, REG_UIC_ERROR_CODE_PHY_ADAPTER_LAYER);\n'
    b'\t\t\tdev_err(hba->dev, "PRE-LINK: TX_FSM=%u UECPA=0x%x IS=0x%x\\n",\n'
    b'\t\t\t\ttx_fsm, uecpa,\n'
    b'\t\t\t\tufshcd_readl(hba, REG_INTERRUPT_STATUS));\n'
    b'\t\t}\n'
)

if old_diag2 in data:
    data = data.replace(old_diag2, b'\n', 1)
    print('Removed PRE-LINK diagnostic from hce_enable_notify PRE_CHANGE')
else:
    print('ERROR: PRE-LINK block not found in expected location')
    idx = data.find(b'PRE-LINK: TX_FSM')
    print(f'  PRE-LINK found at offset {idx}')
    print(repr(data[idx-200:idx+50]))
    import sys; sys.exit(1)

# Add PRE-LINK diagnostic to link_startup_notify PRE_CHANGE, just before
# the ufshcd_disable_host_tx_lcc call (after HCE is done, UIC is ready)
old_lcc = (
    b'\t\terr = ufshcd_disable_host_tx_lcc(hba);\n'
    b'\n'
    b'\n'
    b'\t\tbreak;\n'
)
# Try simpler match
old_lcc2 = b'\t\terr = ufshcd_disable_host_tx_lcc(hba);\n'

# Find the link_startup_notify function and insert diagnostic after disable_lcc
idx = data.find(b'ufs_qcom_link_startup_notify')
if idx < 0:
    print('ERROR: link_startup_notify not found')
    import sys; sys.exit(1)

# Find the first disable_host_tx_lcc after link_startup_notify
lcc_idx = data.find(b'ufshcd_disable_host_tx_lcc(hba);', idx)
if lcc_idx < 0:
    print('ERROR: disable_host_tx_lcc not found after link_startup_notify')
    import sys; sys.exit(1)

# Find the end of that line
line_end = data.find(b'\n', lcc_idx) + 1
diag_insert = (
    b'\n'
    b'\t\t/* PRE-LINK diagnostic: log TX_FSM and PHY state (HCE done, UIC ready) */\n'
    b'\t\t{\n'
    b'\t\t\tu32 tx_fsm = 0, uecpa = 0;\n'
    b'\t\t\tufshcd_dme_get(hba, UIC_ARG_MIB_SEL(MPHY_TX_FSM_STATE,\n'
    b'\t\t\t\tUIC_ARG_MPHY_TX_GEN_SEL_INDEX(0)), &tx_fsm);\n'
    b'\t\t\tuecpa = ufshcd_readl(hba, REG_UIC_ERROR_CODE_PHY_ADAPTER_LAYER);\n'
    b'\t\t\tdev_err(hba->dev, "PRE-LINK: TX_FSM=%u UECPA=0x%x IS=0x%x\\n",\n'
    b'\t\t\t\ttx_fsm, uecpa,\n'
    b'\t\t\t\tufshcd_readl(hba, REG_INTERRUPT_STATUS));\n'
    b'\t\t}\n'
)
data = data[:line_end] + diag_insert + data[line_end:]
print(f'Added PRE-LINK diagnostic to link_startup_notify at offset {line_end}')

with open(path, 'wb') as f:
    f.write(data)

print('Done')
print('PRE-LINK in hce_enable_notify:', b'Diagnostic: log TX_FSM_STATE and UECPA before DME_LINK_STARTUP' in data)
print('PRE-LINK in link_startup_notify:', b'PRE-LINK diagnostic: log TX_FSM and PHY state' in data)
