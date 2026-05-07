#!/usr/bin/env python3
path = '/opt/nerveos/build/cepheus/build/linux-4a8d88483/drivers/ufs/core/ufshcd.c'
with open(path, 'rb') as f:
    data = f.read()

q = b'"'
nl = b'\\n'  # literal backslash-n as in C string

target = (
    b'\tif (ret)\n'
    b'\t\tdev_dbg(hba->dev,\n'
    b'\t\t\t' + q + b'dme-link-startup: error code %d' + nl + q + b', ret);\n'
    b'\treturn ret;\n'
    b'}\n'
)

replacement = (
    b'\tif (ret)\n'
    b'\t\tdev_err(hba->dev,\n'
    b'\t\t\t' + q + b'POST-LINK-FAIL: ret=%d IS=0x%x UECPA=0x%x UECDL=0x%x HCS=0x%x' + nl + q + b',\n'
    b'\t\t\tret,\n'
    b'\t\t\tufshcd_readl(hba, REG_INTERRUPT_STATUS),\n'
    b'\t\t\tufshcd_readl(hba, REG_UIC_ERROR_CODE_PHY_ADAPTER_LAYER),\n'
    b'\t\t\tufshcd_readl(hba, REG_UIC_ERROR_CODE_DATA_LINK_LAYER),\n'
    b'\t\t\tufshcd_readl(hba, REG_CONTROLLER_STATUS));\n'
    b'\treturn ret;\n'
    b'}\n'
)

if b'POST-LINK-FAIL' in data:
    print('already present')
elif target not in data:
    print('NOT FOUND')
    idx = data.find(b'dme-link-startup: error')
    print(repr(data[idx-30:idx+60]))
else:
    data = data.replace(target, replacement, 1)
    open(path, 'wb').write(data)
    print('OK')

with open(path, 'rb') as f:
    d = f.read()
print('POST-LINK-FAIL present:', b'POST-LINK-FAIL' in d)
