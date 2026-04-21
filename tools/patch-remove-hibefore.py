#!/usr/bin/env python3
"""Remove HIBERNATE_BEFORE_HCE quirk from advertise_quirks and ufshcd_hba_enable."""

results = []

# 1. Remove from ufs-qcom.c advertise_quirks
path1 = '/opt/hiveos/build/cepheus/build/linux-4a8d88483/drivers/ufs/host/ufs-qcom.c'
with open(path1, 'r') as f:
    c1 = f.read()

old1 = ('\t/* No hardware reset: bootloader left HCE=1 with active HS link.\n'
        '\t * Hibernate the link before HCE reset so normal PHY reinit works. */\n'
        '\tif (!host->core_reset)\n'
        '\t\thba->quirks |= UFSHCD_QUIRK_HIBERNATE_BEFORE_HCE;\n')
new1 = ''
if old1 in c1:
    c1 = c1.replace(old1, new1, 1)
    results.append('ufs-qcom.c advertise_quirks PATCHED OK')
else:
    results.append('ufs-qcom.c advertise_quirks PATTERN NOT FOUND')

with open(path1, 'w') as f:
    f.write(c1)

# 2. Remove HIBERNATE_BEFORE_HCE block from ufshcd_hba_enable in ufshcd.c
path2 = '/opt/hiveos/build/cepheus/build/linux-4a8d88483/drivers/ufs/core/ufshcd.c'
with open(path2, 'r') as f:
    c2 = f.read()

old2 = ('\n\t/*\n'
        '\t * If bootloader left the HC active with an HS link, gracefully\n'
        '\t * hibernate the link before resetting HCE.  This lets the normal\n'
        '\t * ufshcd_hba_execute_hce path run (PHY reinit -> check_hibern8 ->\n'
        '\t * DME_LINK_STARTUP) without fighting an already-active M-PHY.\n'
        '\t */\n'
        '\tif ((hba->quirks & UFSHCD_QUIRK_HIBERNATE_BEFORE_HCE) &&\n'
        '\t    ufshcd_is_hba_active(hba)) {\n'
        '\t\tufshcd_enable_intr(hba, UFSHCD_UIC_MASK);\n'
        '\t\tret = ufshcd_uic_hibern8_enter(hba);\n'
        '\t\tif (ret)\n'
        '\t\t\tdev_warn(hba->dev,\n'
        '\t\t\t\t "Pre-HCE hibernate failed %d, continuing\\n", ret);\n'
        '\t\t/* Clear stale IS bits before HCE reset */\n'
        '\t\tufshcd_writel(hba, ~0U, REG_INTERRUPT_STATUS);\n'
        '\t\tufshcd_disable_intr(hba, UFSHCD_UIC_MASK);\n'
        '\t}\n')
new2 = '\n'
if old2 in c2:
    c2 = c2.replace(old2, new2, 1)
    results.append('ufshcd.c HIBERNATE_BEFORE_HCE block REMOVED OK')
else:
    results.append('ufshcd.c PATTERN NOT FOUND')

with open(path2, 'w') as f:
    f.write(c2)

for r in results:
    print(r)
