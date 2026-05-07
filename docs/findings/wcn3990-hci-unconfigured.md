# WCN3990 Bluetooth: HCI_UNCONFIGURED blocks HCIDEVUP on mainline Linux

**Hardware:** Qualcomm WCN3990 (SM8150 — Snapdragon 855)  
**Kernel:** mainline 6.11 (sm8150-mainline branch)  
**Symptom:** `hciconfig hci0 up` or `HCIDEVUP` ioctl returns `EOPNOTSUPP (95)`

---

## The problem

WCN3990 ships with an NVM file (`crnv21.bin` or `crnv01.bin` depending on firmware
symlinks) that contains an all-zero BD_ADDR (`00:00:00:00:00:00`). The QCA driver
defines `set_bdaddr()`, so the kernel treats a zero BD_ADDR as an unconfigured
device:

```c
/* hci_register_dev() — net/bluetooth/hci_core.c */
if (hdev->set_bdaddr && !bacmp(&hdev->public_addr, BDADDR_ANY))
    hci_dev_set_flag(hdev, HCI_UNCONFIGURED);
```

With `HCI_UNCONFIGURED` set, the standard bring-up path is blocked:

```c
/* hci_dev_open() */
if (hci_dev_test_flag(hdev, HCI_UNCONFIGURED))
    return -EOPNOTSUPP;
```

So every tool that tries to bring up hci0 — `hciconfig`, `bluetoothctl power on`,
`HCIDEVUP` ioctl — fails with `Operation not supported`.

There are no error messages in dmesg. The kernel's BT debug messages require
dynamic debug (`echo 'module bluetooth +p' > .../dynamic_debug/control`) which
is often not available on embedded builds.

---

## What doesn't work

- `HCIDEVUP` ioctl — returns `EOPNOTSUPP`
- `MGMT_OP_SET_POWERED (0x0005)` — returns `MGMT_STATUS_INVALID_INDEX (0x11)` for unconfigured devices
- `MGMT_OP_SET_STATIC_ADDRESS (0x002B)` — no `HCI_MGMT_UNCONFIGURED` handler flag; returns `INVALID_INDEX`
- `MGMT_OP_READ_UNCONF_INDEX_LIST` — note: opcode is `0x0036`, **not** `0x000D` (which is `SET_LE`)

---

## The fix

`MGMT_OP_SET_PUBLIC_ADDRESS (0x0039)` is the only management command that:
1. Has the `HCI_MGMT_UNCONFIGURED` handler flag (works on unconfigured devices)
2. Calls `hdev->set_bdaddr()` → `qca_set_bdaddr()` → writes `EDL_WRITE_BD_ADDR_OPCODE` vendor command
3. Clears `HCI_UNCONFIGURED` on success

After `SET_PUBLIC_ADDRESS` succeeds, `HCIDEVUP` works normally.

### Minimal C implementation

```c
#define AF_BLUETOOTH        31
#define BTPROTO_HCI         1
#define HCI_CHANNEL_CONTROL 3
#define MGMT_INDEX_NONE     0xFFFF
#define MGMT_OP_SET_PUBLIC_ADDRESS 0x0039

struct sockaddr_hci {
    uint16_t hci_family;
    uint16_t hci_dev;
    uint16_t hci_channel;
};

struct mgmt_hdr {
    uint16_t opcode;
    uint16_t index;
    uint16_t len;
} __attribute__((packed));

/* Open management socket bound to HCI_CHANNEL_CONTROL */
int s = socket(AF_BLUETOOTH, SOCK_RAW | SOCK_CLOEXEC, BTPROTO_HCI);
struct sockaddr_hci addr = {
    .hci_family  = AF_BLUETOOTH,
    .hci_dev     = MGMT_INDEX_NONE,  /* 0xFFFF */
    .hci_channel = HCI_CHANNEL_CONTROL,
};
bind(s, (struct sockaddr *)&addr, sizeof(addr));

/* BD_ADDR in little-endian (LSB first): 00:17:F2:xx:xx:xx */
uint8_t bdaddr[6] = { 0x0D, 0x55, 0x55, 0xF2, 0x17, 0x00 };

/* Send SET_PUBLIC_ADDRESS to hci0 (index 0) */
uint8_t buf[sizeof(struct mgmt_hdr) + 6];
struct mgmt_hdr *hdr = (struct mgmt_hdr *)buf;
hdr->opcode = 0x0039;
hdr->index  = 0;       /* hci0 */
hdr->len    = 6;
memcpy(buf + sizeof(*hdr), bdaddr, 6);
send(s, buf, sizeof(buf), 0);

/* Wait for CMD_COMPLETE (event 0x0001), opcode 0x0039, status 0x00 */
/* On success: MGMT_EV_UNCONF_INDEX_REMOVED + MGMT_EV_INDEX_ADDED follow */
```

Wait for `CMD_COMPLETE` with `status=0x00`, then the sequence:
- `ev=0x001e` (`MGMT_EV_UNCONF_INDEX_REMOVED`) — device leaves unconfigured list
- `ev=0x0004` (`MGMT_EV_INDEX_ADDED`) — device appears in configured list

After these events, `HCIDEVUP` and `MGMT_OP_SET_POWERED` both work.

### Using btmgmt (if available)

```bash
btmgmt public-addr 00:17:F2:xx:xx:xx
```

---

## NVM write is persistent

**Critical discovery:** `qca_set_bdaddr()` sends `EDL_WRITE_BD_ADDR_OPCODE`
(`0xFC14`) to the WCN3990. On SM8150 at least, this command writes the BD_ADDR
to the NVM stored on the chip — **not a volatile register**. After the write and
a full power cycle (reboot), the chip loads its NVM with the new address. The kernel
then reads a valid non-zero BD_ADDR, does not set `HCI_UNCONFIGURED`, and hci0
comes UP automatically on the `power_on` workqueue without any userspace
intervention.

This means you only need to run `SET_PUBLIC_ADDRESS` once. After the first
successful write, the device is self-configuring.

---

## Generating an address

The address must be a valid public BD_ADDR:
- Byte 5 (MSB in display order) bit 1 = 0 (locally-administered bit cleared)
- Byte 5 bit 0 = 0 (multicast bit cleared)

A simple approach: use a Qualcomm OUI prefix (`00:17:F2`) and derive the lower
3 bytes from `/etc/machine-id` so the address is stable and unique per device:

```c
static void make_bdaddr(uint8_t addr[6]) {
    int fd = open("/etc/machine-id", O_RDONLY);
    char id[64] = {0};
    read(fd, id, sizeof(id) - 1);
    close(fd);

    uint8_t h[32] = {0};
    for (int i = 0; id[i] && id[i] != '\n'; i++)
        h[i % 32] ^= (uint8_t)id[i];
    for (int i = 0; i < 6; i++)
        addr[i] = h[i] ^ h[i+6] ^ h[i+12] ^ h[i+18];

    /* Qualcomm OUI + clear multicast/local bits */
    addr[5] = 0x00; addr[4] = 0x17; addr[3] = 0xF2;
}
```

---

## Affected hardware

- Qualcomm WCN3990 on SM8150 (Snapdragon 855)
- Likely also WCN3990 on SDM845 (Snapdragon 845) — same chip, same firmware
- Any Qualcomm BT UART combo chip where the NVM ships with zero BD_ADDR

## Kernel version

Confirmed on Linux 6.11 (sm8150-mainline). The `HCI_MGMT_UNCONFIGURED` flag
mechanism has been in the kernel since ~4.15 so this approach should work on
any reasonably modern kernel.

## Related files

- `net/bluetooth/mgmt.c` — `set_public_address()` handler, `HCI_MGMT_UNCONFIGURED` flag
- `drivers/bluetooth/btqca.c` — `qca_set_bdaddr()`, `EDL_WRITE_BD_ADDR_OPCODE`
- `net/bluetooth/hci_core.c` — `HCI_UNCONFIGURED` set in `hci_register_dev()`
