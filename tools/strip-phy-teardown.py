#!/usr/bin/env python3
"""Remove PHY teardown patch from ufs_qcom_power_up_sequence."""

path = '/opt/nerveos/build/cepheus/build/linux-4a8d88483/drivers/ufs/host/ufs-qcom.c'
with open(path, 'rb') as f:
    data = f.read()

old = (b'\t/* Tear down PHY if it was previously initialized (e.g. retry after\n'
       b'\t * link startup failure). BCR reset will clear PHY registers, so we\n'
       b'\t * must reset the refcounts to allow a full hardware reinit. */\n'
       b'\tif (phy->power_count > 0) {\n'
       b'\t\tufs_qcom_disable_lane_clks(host);\n'
       b'\t\tphy_power_off(phy);\n'
       b'\t}\n'
       b'\tif (phy->init_count > 0)\n'
       b'\t\tphy_exit(phy);\n'
       b'\n')

if old in data:
    data = data.replace(old, b'\n', 1)
    with open(path, 'wb') as f:
        f.write(data)
    print('STRIPPED OK - PHY teardown removed')
else:
    idx = data.find(b'Tear down PHY')
    print('Not found, context:')
    if idx >= 0:
        print(repr(data[idx-10:idx+300]))
    else:
        print('Tear down PHY not found')
        # Show what's in power_up_sequence
        idx2 = data.find(b'ufs_qcom_power_up_sequence')
        print(repr(data[idx2:idx2+400]))
