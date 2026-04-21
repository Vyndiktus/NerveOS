#!/usr/bin/env python3
"""Strip ALL our patches - return to clean mainline kernel state."""

# Strip POST-LINK-FAIL from ufshcd.c
ufshcd_path = '/opt/hiveos/build/cepheus/build/linux-4a8d88483/drivers/ufs/core/ufshcd.c'
with open(ufshcd_path, 'rb') as f:
    data = f.read()

old = (b'\n\t\tif (ret)\n'
       b'\t\t\tdev_err(hba->dev,\n'
       b'\t\t\t\t"POST-LINK-FAIL: ret=%d IS=0x%x UECPA=0x%x UECDL=0x%x HCS=0x%x\\n",\n'
       b'\t\t\t\tret,\n'
       b'\t\t\t\tufshcd_readl(hba, REG_INTERRUPT_STATUS),\n'
       b'\t\t\t\tufshcd_readl(hba, REG_UIC_ERROR_CODE_PHY_ADAPTER_LAYER),\n'
       b'\t\t\t\tufshcd_readl(hba, REG_UIC_ERROR_CODE_DATA_LINK_LAYER),\n'
       b'\t\t\t\tufshcd_readl(hba, REG_CONTROLLER_STATUS));\n')

if old in data:
    data = data.replace(old, b'\n', 1)
    print('ufshcd.c: POST-LINK-FAIL stripped OK')
else:
    idx = data.find(b'POST-LINK-FAIL')
    if idx >= 0:
        print('POST-LINK-FAIL found but pattern mismatch:')
        print(repr(data[idx-50:idx+200]))
    else:
        print('ufshcd.c: POST-LINK-FAIL already stripped or not present')

with open(ufshcd_path, 'wb') as f:
    f.write(data)

print('Done. All patches stripped.')
print('Remaining in ufshcd.c:', b'POST-LINK-FAIL' in data)
print('Remaining in ufs-qcom.c PRE-LINK:', open('/opt/hiveos/build/cepheus/build/linux-4a8d88483/drivers/ufs/host/ufs-qcom.c', 'rb').read().find(b'PRE-LINK:') >= 0)
print('Remaining in ufs-qcom.c teardown:', open('/opt/hiveos/build/cepheus/build/linux-4a8d88483/drivers/ufs/host/ufs-qcom.c', 'rb').read().find(b'Tear down PHY') >= 0)
