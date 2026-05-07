#!/usr/bin/env python3
"""Re-apply PHY teardown patch before ufs_qcom_host_reset call."""

path = '/opt/nerveos/build/cepheus/build/linux-4a8d88483/drivers/ufs/host/ufs-qcom.c'
with open(path, 'rb') as f:
    data = f.read()

if b'Tear down PHY' in data:
    print('PHY teardown already present')
    exit(0)

# Inject before "/* Reset UFS Host Controller and PHY */"
target = b'\t/* Reset UFS Host Controller and PHY */\n\tret = ufs_qcom_host_reset(hba);\n'
teardown = (
    b'\t/* Tear down PHY if it was previously initialized (e.g. retry after\n'
    b'\t * link startup failure). BCR reset will clear PHY registers, so we\n'
    b'\t * must reset the refcounts to allow a full hardware reinit. */\n'
    b'\tif (phy->power_count > 0) {\n'
    b'\t\tufs_qcom_disable_lane_clks(host);\n'
    b'\t\tphy_power_off(phy);\n'
    b'\t}\n'
    b'\tif (phy->init_count > 0)\n'
    b'\t\tphy_exit(phy);\n'
    b'\n'
)

if target not in data:
    print('ERROR: injection point not found')
    idx = data.find(b'ufs_qcom_host_reset')
    print('Context:', repr(data[idx-100:idx+50]))
    exit(1)

data = data.replace(target, teardown + target, 1)
with open(path, 'wb') as f:
    f.write(data)
print('PHY teardown patch applied OK')
print('Tear down PHY present:', b'Tear down PHY' in data)
