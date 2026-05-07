#!/usr/bin/env python3
"""Fix literal newline in dev_err format string in ufs-qcom.c diagnostic block."""

path = '/opt/nerveos/build/cepheus/build/linux-4a8d88483/drivers/ufs/host/ufs-qcom.c'
with open(path, 'rb') as f:
    data = f.read()

# The bad pattern has a literal \n (0x0a) inside the string literal
bad = b'"PRE-LINK: TX_FSM=%u UECPA=0x%x IS=0x%x\n",'
good = b'"PRE-LINK: TX_FSM=%u UECPA=0x%x IS=0x%x\\n",'

if bad in data:
    data = data.replace(bad, good, 1)
    with open(path, 'wb') as f:
        f.write(data)
    print('FIXED')
else:
    idx = data.find(b'PRE-LINK')
    print('Not found, context:', repr(data[idx-5:idx+70]))
