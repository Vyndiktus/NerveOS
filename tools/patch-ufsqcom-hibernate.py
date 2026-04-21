#!/usr/bin/env python3
"""Patch ufs-qcom.c: replace BROKEN_HCE+SKIP_LINK_STARTUP with HIBERNATE_BEFORE_HCE,
   remove bootloader_phy_preserved PHY skip, clean up reinit_notify."""
import sys

path = '/opt/hiveos/build/cepheus/build/linux-4a8d88483/drivers/ufs/host/ufs-qcom.c'
with open(path, 'r') as f:
    content = f.read()

results = []

# 1. Replace advertise_quirks: BROKEN_HCE + SKIP_LINK_STARTUP → HIBERNATE_BEFORE_HCE
old1 = ('\t\t/* No hardware reset: bootloader left HCE=1, avoid clearing it */\n'
        '\t\tif (!host->core_reset) {\n'
        '\t\t\thba->quirks |= UFSHCI_QUIRK_BROKEN_HCE;\n'
        '\t\t\thba->quirks |= UFSHCD_QUIRK_SKIP_LINK_STARTUP;\n'
        '\t\t}')
new1 = ('\t\t/* No hardware reset: bootloader left HCE=1 with active HS link.\n'
        '\t\t * Hibernate the link before HCE reset so normal PHY reinit works. */\n'
        '\t\tif (!host->core_reset)\n'
        '\t\t\thba->quirks |= UFSHCD_QUIRK_HIBERNATE_BEFORE_HCE;')
if old1 in content:
    content = content.replace(old1, new1, 1)
    results.append('advertise_quirks PATCHED OK')
else:
    results.append('advertise_quirks PATTERN NOT FOUND')

# 2. Remove bootloader_phy_preserved early return from ufs_qcom_power_up_sequence
old2 = ('\n\t/* If bootloader PHY state is preserved, skip PHY re-init */\n'
        '\tif (host->bootloader_phy_preserved) {\n'
        '\t\tufs_qcom_select_unipro_mode(host);\n'
        '\t\treturn 0;\n'
        '\t}\n')
new2 = '\n'
if old2 in content:
    content = content.replace(old2, new2, 1)
    results.append('power_up_sequence bootloader skip REMOVED OK')
else:
    results.append('power_up_sequence PATTERN NOT FOUND')

# 3. Clean up reinit_notify: remove BROKEN_HCE + SKIP_LINK_STARTUP clearing
old3 = ('\t/* Gear switch reinit needs full HCE + PHY re-initialization */\n'
        '\thba->quirks &= ~(UFSHCI_QUIRK_BROKEN_HCE | UFSHCD_QUIRK_SKIP_LINK_STARTUP);\n'
        '\thost->bootloader_phy_preserved = false;\n'
        '\tphy_power_off(host->generic_phy);')
new3 = ('\t/* Gear switch reinit needs full HCE + PHY re-initialization */\n'
        '\thba->quirks &= ~UFSHCD_QUIRK_HIBERNATE_BEFORE_HCE;\n'
        '\tphy_power_off(host->generic_phy);')
if old3 in content:
    content = content.replace(old3, new3, 1)
    results.append('reinit_notify PATCHED OK')
else:
    results.append('reinit_notify PATTERN NOT FOUND')

with open(path, 'w') as f:
    f.write(content)

for r in results:
    print(r)
