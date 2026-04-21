#!/usr/bin/env python3
"""
Patch ufs-qcom.c to preserve bootloader PHY state on first link startup.
BCR reset + mainline PHY re-init doesn't produce a working PHY state on SM8150.
Instead: first boot uses bootloader's config, retries do full mainline re-init.
"""

path = '/opt/hiveos/build/cepheus/build/linux-4a8d88483/drivers/ufs/host/ufs-qcom.c'
with open(path, 'rb') as f:
    data = f.read()

# Change 1: Always set bootloader_phy_preserved = true at probe time.
# (was: !host->core_reset which evaluates to false when GCC_UFS_PHY_BCR reset exists)
old1 = b'\thost->bootloader_phy_preserved = !host->core_reset;\n'
new1 = b'\thost->bootloader_phy_preserved = true;\n'
if old1 not in data:
    print('ERROR: bootloader_phy_preserved init line not found')
    import sys; sys.exit(1)
data = data.replace(old1, new1, 1)
print('Change 1 applied: bootloader_phy_preserved always true at probe')

# Change 2: In ufs_qcom_power_up_sequence, skip BCR reset + PHY reinit on
# first boot. Insert early-return check before the PHY teardown/reset block.
# Target: the start of our existing teardown patch (the comment before if phy->power_count)
old2 = (
    b'\t/* Tear down PHY if it was previously initialized (e.g. retry after\n'
    b'\t * link startup failure). BCR reset will clear PHY registers, so we\n'
    b'\t * must reset the refcounts to allow a full hardware reinit. */\n'
)
new2 = (
    b'\t/*\n'
    b'\t * On first boot the bootloader already configured the QMP UFS PHY\n'
    b'\t * correctly. Doing BCR reset + mainline re-init overwrites working\n'
    b'\t * register values and causes PA_PHY_GENERIC_ERROR on SM8150.\n'
    b'\t * Skip re-init on first call; subsequent retries do full re-init.\n'
    b'\t */\n'
    b'\tif (host->bootloader_phy_preserved) {\n'
    b'\t\thost->bootloader_phy_preserved = false;\n'
    b'\t\tdev_info(hba->dev, "ufs-qcom: using bootloader PHY config\\n");\n'
    b'\t\tufs_qcom_select_unipro_mode(host);\n'
    b'\t\treturn 0;\n'
    b'\t}\n'
    b'\n'
    b'\t/* Tear down PHY if it was previously initialized (e.g. retry after\n'
    b'\t * link startup failure). BCR reset will clear PHY registers, so we\n'
    b'\t * must reset the refcounts to allow a full hardware reinit. */\n'
)
if old2 not in data:
    print('ERROR: teardown comment not found')
    import sys; sys.exit(1)
data = data.replace(old2, new2, 1)
print('Change 2 applied: early-return for first boot in power_up_sequence')

with open(path, 'wb') as f:
    f.write(data)

print('Patch applied OK')
print('bootloader_phy_preserved check present:',
      b'bootloader_phy_preserved' in data)
print('early return present:',
      b'using bootloader PHY config' in data)
