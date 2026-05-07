#!/usr/bin/env python3
"""Add post-failure UECPA diagnostic right after dme_link_startup fails in ufshcd.c."""

path = '/opt/nerveos/build/cepheus/build/linux-4a8d88483/drivers/ufs/core/ufshcd.c'
with open(path) as f:
    c = f.read()

old = (
    '\t\tret = ufshcd_dme_link_startup(hba);\n'
    '\n'
    '\t\t/* check if device is detected by inter-connect layer */'
)

new = (
    '\t\tret = ufshcd_dme_link_startup(hba);\n'
    '\n'
    '\t\tif (ret)\n'
    '\t\t\tdev_err(hba->dev,\n'
    '\t\t\t\t"POST-LINK-FAIL: ret=%d IS=0x%x UECPA=0x%x UECDL=0x%x HCS=0x%x\\n",\n'
    '\t\t\t\tret,\n'
    '\t\t\t\tufshcd_readl(hba, REG_INTERRUPT_STATUS),\n'
    '\t\t\t\tufshcd_readl(hba, REG_UIC_ERROR_CODE_PHY_ADAPTER_LAYER),\n'
    '\t\t\t\tufshcd_readl(hba, REG_UIC_ERROR_CODE_DATA_LINK_LAYER),\n'
    '\t\t\t\tufshcd_readl(hba, REG_CONTROLLER_STATUS));\n'
    '\n'
    '\t\t/* check if device is detected by inter-connect layer */'
)

if old in c:
    c = c.replace(old, new, 1)
    with open(path, 'w') as f:
        f.write(c)
    print('PATCHED OK')
else:
    print('PATTERN NOT FOUND')
    idx = c.find('ufshcd_dme_link_startup')
    print(repr(c[idx:idx+200]))
