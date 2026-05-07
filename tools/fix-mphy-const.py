#!/usr/bin/env python3
path = '/opt/nerveos/build/cepheus/build/linux-4a8d88483/drivers/ufs/core/ufshcd.c'
with open(path) as f:
    text = f.read()

old = ('\t\tu32 tx_fsm = 0;\n'
       '\t\tufshcd_dme_get(hba, UIC_ARG_MIB_SEL(MPHY_TX_FSM_STATE,\n'
       '\t\t\tUIC_ARG_MPHY_TX_GEN_SEL_INDEX(0)), &tx_fsm);')
new = ('\t\tu32 tx_fsm = 0;\n'
       '\t\tufshcd_dme_get(hba, UIC_ARG_MIB_SEL(0x41,\n'
       '\t\t\tUIC_ARG_MPHY_TX_GEN_SEL_INDEX(0)), &tx_fsm);')

if old not in text:
    print('NOT FOUND')
    exit(1)
text = text.replace(old, new, 1)
with open(path, 'w') as f:
    f.write(text)
print('OK - MPHY_TX_FSM_STATE replaced with 0x41')
