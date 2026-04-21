#!/usr/bin/env python3
"""Patch ufshcd.c to add HIBERNATE_BEFORE_HCE logic before BROKEN_HCE check."""
import sys

path = '/opt/hiveos/build/cepheus/build/linux-4a8d88483/drivers/ufs/core/ufshcd.c'
with open(path, 'r') as f:
    content = f.read()

old = 'int ufshcd_hba_enable(struct ufs_hba *hba)\n{\n\tint ret;\n\n\tif (hba->quirks & UFSHCI_QUIRK_BROKEN_HCE) {'

new = ('int ufshcd_hba_enable(struct ufs_hba *hba)\n'
       '{\n'
       '\tint ret;\n'
       '\n'
       '\t/*\n'
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
       '\t}\n'
       '\n'
       '\tif (hba->quirks & UFSHCI_QUIRK_BROKEN_HCE) {')

if old in content:
    content = content.replace(old, new, 1)
    with open(path, 'w') as f:
        f.write(content)
    print('PATCHED OK')
else:
    # Show context for debugging
    idx = content.find('int ufshcd_hba_enable')
    print('PATTERN NOT FOUND')
    print('Found function at:', idx)
    if idx >= 0:
        print(repr(content[idx:idx+200]))
