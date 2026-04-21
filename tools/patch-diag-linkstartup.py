#!/usr/bin/env python3
"""Add TX_FSM_STATE and UECPA diagnostic before DME_LINK_STARTUP."""

path = '/opt/hiveos/build/cepheus/build/linux-4a8d88483/drivers/ufs/host/ufs-qcom.c'
with open(path) as f:
    c = f.read()

old = '\t\terr = ufshcd_disable_host_tx_lcc(hba);\n\n\t\tbreak;\n\tdefault:'

new = (
    '\t\terr = ufshcd_disable_host_tx_lcc(hba);\n'
    '\n'
    '\t\t/* Diag: log TX_FSM and UECPA right before DME_LINK_STARTUP */\n'
    '\t\t{\n'
    '\t\t\tu32 tx_fsm = 0xff, uecpa;\n'
    '\t\t\tufshcd_dme_get(hba, UIC_ARG_MIB_SEL(MPHY_TX_FSM_STATE,\n'
    '\t\t\t\tUIC_ARG_MPHY_TX_GEN_SEL_INDEX(0)), &tx_fsm);\n'
    '\t\t\tuecpa = ufshcd_readl(hba,\n'
    '\t\t\t\tREG_UIC_ERROR_CODE_PHY_ADAPTER_LAYER);\n'
    '\t\t\tdev_err(hba->dev,\n'
    '\t\t\t\t"PRE-LINK: TX_FSM=%u UECPA=0x%x IS=0x%x\\n",\n'
    '\t\t\t\ttx_fsm, uecpa,\n'
    '\t\t\t\tufshcd_readl(hba, REG_INTERRUPT_STATUS));\n'
    '\t\t}\n'
    '\n'
    '\t\tbreak;\n'
    '\tdefault:'
)

if old in c:
    c = c.replace(old, new, 1)
    with open(path, 'w') as f:
        f.write(c)
    print('PATCHED OK')
else:
    print('PATTERN NOT FOUND')
    # Show context
    idx = c.find('ufshcd_disable_host_tx_lcc')
    print(repr(c[idx:idx+200]))
