#!/usr/bin/env python3
"""Patch ufs-qcom.c with exact patterns."""

path = '/opt/hiveos/build/cepheus/build/linux-4a8d88483/drivers/ufs/host/ufs-qcom.c'
with open(path, 'r') as f:
    content = f.read()

results = []

# 1. Replace advertise_quirks block
old1 = ('\t/* No hardware reset: bootloader left HCE=1, avoid clearing it */\n'
        '\tif (!host->core_reset) {\n'
        '\t\thba->quirks |= UFSHCI_QUIRK_BROKEN_HCE;\n'
        '\t\thba->quirks |= UFSHCD_QUIRK_SKIP_LINK_STARTUP;\n'
        '\t}\n'
        '}')
new1 = ('\t/* No hardware reset: bootloader left HCE=1 with active HS link.\n'
        '\t * Hibernate the link before HCE reset so normal PHY reinit works. */\n'
        '\tif (!host->core_reset)\n'
        '\t\thba->quirks |= UFSHCD_QUIRK_HIBERNATE_BEFORE_HCE;\n'
        '}')
if old1 in content:
    content = content.replace(old1, new1, 1)
    results.append('advertise_quirks PATCHED OK')
else:
    results.append('advertise_quirks PATTERN NOT FOUND')

# 2. Clean up reinit_notify
old3 = ('\t/* Gear switch reinit needs full HCE + PHY re-initialization */\n'
        '\thba->quirks &= ~(UFSHCI_QUIRK_BROKEN_HCE | UFSHCD_QUIRK_SKIP_LINK_STARTUP);\n'
        '\thost->bootloader_phy_preserved = false;\n'
        '\n'
        '\tphy_power_off(host->generic_phy);')
new3 = ('\t/* Gear switch reinit needs full HCE + PHY re-initialization */\n'
        '\thba->quirks &= ~UFSHCD_QUIRK_HIBERNATE_BEFORE_HCE;\n'
        '\n'
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
