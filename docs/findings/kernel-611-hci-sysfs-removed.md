# Kernel 6.11: HCI Bluetooth sysfs attributes removed — use management socket

**Kernel:** mainline 6.11+  
**Symptom:** `/sys/class/bluetooth/hci0/address`, `name`, `type`, `features` don't exist

---

## What changed

In kernel 6.11, the HCI device sysfs attributes that were historically exported
under `/sys/class/bluetooth/hciX/` were removed. The directory now contains only
the standard kobject entries:

```
/sys/class/bluetooth/hci0/
├── device -> ../../../serial0-0   (symlink to underlying device)
├── power/                         (standard PM directory)
├── rfkill0/                       (rfkill interface)
├── subsystem -> ...               (symlink)
└── uevent                         (kobject uevent file)
```

Notably absent compared to older kernels:
- `address` — BD_ADDR
- `name` — device name
- `type` — BR/EDR, LE, AMP
- `features` — LMP feature bits
- `manufacturer`
- `bus`

`find /sys/class/bluetooth/hci0 -type f` returns nothing useful.

---

## How to get controller information now

Use the BlueZ Management API (MGMT socket). This is the authoritative interface
and works regardless of kernel version.

### With btmgmt (if installed)
```bash
btmgmt info
```

### With bluetoothctl
```bash
bluetoothctl show
```

### Programmatically via MGMT socket (C)

Open a socket on `HCI_CHANNEL_CONTROL` and send `MGMT_OP_READ_INFO (0x0004)`:

```c
#define AF_BLUETOOTH        31
#define BTPROTO_HCI         1
#define HCI_CHANNEL_CONTROL 3
#define MGMT_INDEX_NONE     0xFFFF

/* mgmt_rp_read_info — kernel layout (include/net/bluetooth/mgmt.h):
 * Note: field order differs from older BlueZ documentation */
struct mgmt_rp_read_info {
    uint8_t  bdaddr[6];          /* BD_ADDR, LSB first */
    uint8_t  version;            /* BT spec version: 0x09 = BT 5.0 */
    uint16_t manufacturer;       /* 0x001d = Qualcomm */
    uint32_t supported_settings; /* capability bitmask */
    uint32_t current_settings;   /* active settings bitmask */
    uint8_t  dev_class[3];
    uint8_t  name[249];          /* MGMT_MAX_NAME_LENGTH */
    uint8_t  short_name[11];     /* MGMT_MAX_SHORT_NAME_LENGTH */
} __attribute__((packed));
```

**Common mistake:** older BlueZ API documentation shows `revision` after `version`
and `supported_settings` after `name`/`short_name`. The actual kernel struct
(verified in `include/net/bluetooth/mgmt.h`, kernel 6.11) has `manufacturer`
after `version` and `supported_settings`/`current_settings` before `dev_class`
and `name`. Getting this wrong produces zeroes for the settings fields while
other fields look plausible.

### current_settings bitmask (selected bits)

```c
#define MGMT_SETTING_POWERED       (1 << 0)
#define MGMT_SETTING_CONNECTABLE   (1 << 1)
#define MGMT_SETTING_DISCOVERABLE  (1 << 3)
#define MGMT_SETTING_SSP           (1 << 6)
#define MGMT_SETTING_BREDR         (1 << 7)
#define MGMT_SETTING_LE            (1 << 9)
#define MGMT_SETTING_SC            (1 << 11)  /* Secure Connections */
```

A fully operational BT 5.0 controller with bluetoothd running shows:
`0x00000ac1` = `POWERED | SSP | BREDR | LE | SC`

---

## Checking whether hci0 is UP without sysfs

`HCIDEVUP` ioctl returns `EALREADY (-114)` when `HCI_UP` is set:

```c
int s = socket(AF_BLUETOOTH, SOCK_RAW, BTPROTO_HCI);
int ret = ioctl(s, HCIDEVUP, dev_id);
if (ret < 0 && errno == EALREADY)
    printf("hci%d is already UP\n", dev_id);
```

Or check `MGMT_OP_READ_INFO` — if `current_settings & MGMT_SETTING_POWERED` is
set, the device is UP.

---

## Script one-liner (Python, requires python-dbus or raw socket)

```python
import socket, struct

AF_BLUETOOTH = 31; BTPROTO_HCI = 1; HCI_CHANNEL_CONTROL = 3

s = socket.socket(AF_BLUETOOTH, socket.SOCK_RAW | socket.SOCK_CLOEXEC, BTPROTO_HCI)
# Note: Python socket.bind() does not support AF_BLUETOOTH CHANNEL_CONTROL directly.
# Use ctypes to call bind() with the raw sockaddr_hci struct.
import ctypes, ctypes.util
libc = ctypes.CDLL(ctypes.util.find_library('c'))

class SockaddrHCI(ctypes.Structure):
    _pack_ = 1
    _fields_ = [('family', ctypes.c_uint16),
                ('dev',    ctypes.c_uint16),
                ('channel',ctypes.c_uint16)]

addr = SockaddrHCI(family=AF_BLUETOOTH, dev=0xFFFF, channel=HCI_CHANNEL_CONTROL)
libc.bind(s.fileno(), ctypes.byref(addr), ctypes.sizeof(addr))
s.settimeout(5)
s.send(struct.pack('<HHH', 0x0004, 0, 0))  # READ_INFO, hci0, len=0

data = s.recv(512)
ev, idx, ln, op, st = struct.unpack_from('<HHHH B', data)
if ev == 1 and op == 0x0004 and st == 0:
    bd = data[9:15]
    settings = struct.unpack_from('<I', data, 13)[0]
    print('BD_ADDR:', ':'.join('%02X' % b for b in reversed(bd)))
    print('POWERED:', bool(settings & 1))
    print('LE:     ', bool(settings & (1<<9)))
```

---

## Background

The removal was part of a broader cleanup to consolidate Bluetooth management
through the management socket (introduced in BlueZ 5.x / kernel 3.4). The sysfs
attributes duplicated information already available via MGMT and were not being
actively maintained. Tools that relied on them (old versions of `hciconfig`,
scripts parsing `/sys/class/bluetooth/hciX/address`) need to be updated to use
the management socket or BlueZ D-Bus API.
