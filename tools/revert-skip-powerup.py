#!/usr/bin/env python3
"""Revert the skip_power_up_once changes - crashes device."""

c_path = '/opt/nerveos/build/cepheus/build/linux-4a8d88483/drivers/ufs/host/ufs-qcom.c'
h_path = '/opt/nerveos/build/cepheus/build/linux-4a8d88483/drivers/ufs/host/ufs-qcom.h'

# Revert PRE_CHANGE handler
with open(c_path, 'rb') as f:
    data = f.read()

old_pre = (
    b'\tcase PRE_CHANGE:\n'
    b'\t\tif (host->skip_power_up_once) {\n'
    b'\t\t\t/* First HCE: ABL left QMP PHY fully calibrated and lane\n'
    b'\t\t\t * clocks running. Touch nothing \xe2\x80\x94 let HCE proceed with\n'
    b'\t\t\t * ABL\'s complete PHY state. Retries do full reinit. */\n'
    b'\t\t\thost->skip_power_up_once = false;\n'
    b'\t\t\terr = 0;\n'
    b'\t\t} else {\n'
    b'\t\t\terr = ufs_qcom_power_up_sequence(hba);\n'
    b'\t\t\tif (err)\n'
    b'\t\t\t\treturn err;\n'
    b'\t\t\terr = ufs_qcom_enable_lane_clks(host);\n'
    b'\t\t}\n'
    b'\t\tbreak;\n'
)

# Fallback: check for the other version of the comment (ASCII em dash)
old_pre_v2 = (
    b'\tcase PRE_CHANGE:\n'
    b'\t\tif (host->skip_power_up_once) {\n'
)

new_pre = (
    b'\tcase PRE_CHANGE:\n'
    b'\t\terr = ufs_qcom_power_up_sequence(hba);\n'
    b'\t\tif (err)\n'
    b'\t\t\treturn err;\n'
    b'\n'
    b'\t\t/*\n'
    b'\t\t * The PHY PLL output is the source of tx/rx lane symbol\n'
    b'\t\t * clocks, hence, enable the lane clocks only after PHY\n'
    b'\t\t * is initialized.\n'
    b'\t\t */\n'
    b'\t\terr = ufs_qcom_enable_lane_clks(host);\n'
    b'\t\tbreak;\n'
)

if old_pre in data:
    data = data.replace(old_pre, new_pre, 1)
    print('PRE_CHANGE reverted OK')
else:
    # Find and show what's there
    idx = data.find(b'skip_power_up_once')
    if idx >= 0:
        print('Found skip_power_up_once at:', idx)
        print(repr(data[idx-50:idx+200]))
    else:
        print('skip_power_up_once not found in PRE_CHANGE - may already be reverted')

# Remove init line
old_init = b'\thost->skip_power_up_once = true; /* preserve ABL PHY on first HCE */\n'
if old_init in data:
    data = data.replace(old_init, b'', 1)
    print('init line removed OK')
else:
    print('init line not found - may already be removed')

with open(c_path, 'wb') as f:
    f.write(data)

# Remove struct field from header
with open(h_path, 'rb') as f:
    hdata = f.read()

old_field = b'\tbool skip_power_up_once;\n'
if old_field in hdata:
    hdata = hdata.replace(old_field, b'', 1)
    with open(h_path, 'wb') as f:
        f.write(hdata)
    print('struct field removed OK')
else:
    print('struct field not found - may already be removed')
