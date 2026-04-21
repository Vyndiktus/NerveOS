#!/usr/bin/env python3
"""Skip ufs_qcom_power_up_sequence on first HCE to preserve ABL's PHY calibration.

On first boot, ABL left the QMP UFS PHY fully programmed and the link in HS.
Our re-init via qmp_ufs tables yields UECPA=0x80000010 (host PHY generic error).
By skipping power_up_sequence on the first call we let ABL's calibration stand;
HCE reset clears UFSHCI + M-PHY state machine but keeps PHY hardware registers.
Retries still do full reinit (BCR reset + phy_init + phy_power_on).
"""

h_path = '/opt/hiveos/build/cepheus/build/linux-4a8d88483/drivers/ufs/host/ufs-qcom.h'
c_path = '/opt/hiveos/build/cepheus/build/linux-4a8d88483/drivers/ufs/host/ufs-qcom.c'

# 1. Add skip_power_up_once field to struct in ufs-qcom.h
with open(h_path) as f:
    h = f.read()

old_h = '\tbool bootloader_phy_preserved;\n};'
new_h = '\tbool bootloader_phy_preserved;\n\tbool skip_power_up_once;\n};'

if old_h in h:
    h = h.replace(old_h, new_h, 1)
    with open(h_path, 'w') as f:
        f.write(h)
    print('ufs-qcom.h: struct field added OK')
elif 'skip_power_up_once' in h:
    print('ufs-qcom.h: field already present')
else:
    print('ufs-qcom.h: PATTERN NOT FOUND')
    idx = h.find('bootloader_phy_preserved')
    print(repr(h[idx-10:idx+80]))

# 2. Initialize the flag in ufs_qcom_init (after bootloader_phy_preserved)
with open(c_path) as f:
    c = f.read()

old_init = '\thost->bootloader_phy_preserved = !host->core_reset;\n'
new_init = ('\thost->bootloader_phy_preserved = !host->core_reset;\n'
            '\thost->skip_power_up_once = true; /* preserve ABL PHY on first HCE */\n')

if old_init in c and 'skip_power_up_once = true' not in c:
    c = c.replace(old_init, new_init, 1)
    print('ufs-qcom.c: skip_power_up_once init added OK')
elif 'skip_power_up_once = true' in c:
    print('ufs-qcom.c: init already present')
else:
    print('ufs-qcom.c: init PATTERN NOT FOUND')

# 3. Modify hce_enable_notify PRE_CHANGE to skip on first call
old_pre = (
    '\tcase PRE_CHANGE:\n'
    '\t\terr = ufs_qcom_power_up_sequence(hba);\n'
    '\t\tif (err)\n'
    '\t\t\treturn err;\n'
    '\n'
    '\t\t/*\n'
    '\t\t * The PHY PLL output is the source of tx/rx lane symbol\n'
    '\t\t * clocks, hence, enable the lane clocks only after PHY\n'
    '\t\t * is initialized.\n'
    '\t\t */\n'
    '\t\terr = ufs_qcom_enable_lane_clks(host);\n'
    '\t\tbreak;\n'
)

new_pre = (
    '\tcase PRE_CHANGE:\n'
    '\t\tif (host->skip_power_up_once) {\n'
    '\t\t\t/* First HCE: ABL left QMP PHY calibrated. HCE clears UFSHCI\n'
    '\t\t\t * and M-PHY state machine but PHY hardware regs are intact.\n'
    '\t\t\t * Skip phy_init/phy_power_on; just ensure lane clocks on. */\n'
    '\t\t\thost->skip_power_up_once = false;\n'
    '\t\t\terr = ufs_qcom_enable_lane_clks(host);\n'
    '\t\t} else {\n'
    '\t\t\terr = ufs_qcom_power_up_sequence(hba);\n'
    '\t\t\tif (err)\n'
    '\t\t\t\treturn err;\n'
    '\t\t\terr = ufs_qcom_enable_lane_clks(host);\n'
    '\t\t}\n'
    '\t\tbreak;\n'
)

if old_pre in c:
    c = c.replace(old_pre, new_pre, 1)
    print('ufs-qcom.c: PRE_CHANGE handler patched OK')
elif 'skip_power_up_once' in c and 'skip_power_up_once = false' in c:
    print('ufs-qcom.c: PRE_CHANGE already patched')
else:
    print('ufs-qcom.c: PRE_CHANGE PATTERN NOT FOUND')
    idx = c.find('case PRE_CHANGE:\n\t\terr = ufs_qcom_power_up_sequence')
    if idx >= 0:
        print(repr(c[idx:idx+300]))
    else:
        idx = c.find('ufs_qcom_power_up_sequence')
        print(repr(c[idx:idx+200]))

with open(c_path, 'w') as f:
    f.write(c)
print('Done.')
