# Mainline Linux Bluetooth on SM8150 (Snapdragon 855): complete setup guide

**Hardware:** Qualcomm SM8150 + WCN3990  
**Tested on:** Xiaomi Mi 9 (cepheus), kernel 6.11 (sm8150-mainline)  
**Result:** hci0 UP, BT 5.0, BREDR + LE, bluetoothd 5.72 running

This consolidates everything needed to get Bluetooth working from scratch. Each
section has a companion write-up with deeper detail.

---

## 1. DTS: enable the BT UART node

The WCN3990 BT interface is a serdev device on UART13 (`c8c000.serial`). Add a
`bluetooth` child to the `&uart13` node:

```dts
&uart13 {
    status = "okay";

    bluetooth: bluetooth {
        compatible = "qcom,wcn3990-bt";
        vddio-supply  = <&vreg_l12a_1p8>;
        vddxo-supply  = <&vreg_l7a_1p8>;
        vddrf-supply  = <&vreg_l2c_1p3>;
        vddch0-supply = <&vreg_l11c_3p3>;
        max-speed = <3200000>;
    };
};
```

No GPIO for BT enable on cepheus — WCN3990 is powered entirely via regulators.

---

## 2. Kernel config

```
CONFIG_BT=y
CONFIG_BT_HCIUART=y
CONFIG_BT_HCIUART_QCA=y
CONFIG_BT_QCA=y
```

If building for SM8150 with ABL (UEFI bootloader), also add:
```
CONFIG_EFI=n
CONFIG_EFI_STUB=n
```
Without this, ABL provides its own DTB via the EFI system table, silently
overriding your appended DTB and ignoring your DTS changes. See the companion
write-up on this.

---

## 3. Firmware files

From `linux-firmware.git`, place in `/lib/firmware/qca/`:
- `crbtfw21.tlv` — WCN3990 patch firmware
- `crnv21.bin` — WCN3990 NVM (config)

SM8150 chips typically report firmware version `0x01`, so the driver requests
`crbtfw01.tlv` and `crnv01.bin`. Create symlinks:

```bash
cd /lib/firmware/qca
ln -sf crbtfw21.tlv crbtfw01.tlv
ln -sf crnv21.bin   crnv01.bin
```

---

## 4. Fix the GENI UART DMA re-arm bug

On cold boots, a spurious DMA interrupt fires with `SE_DMA_RX_LEN_IN = 0`. The
current kernel code returns early without re-arming the DMA, leaving UART RX
permanently dead. Symptom: "Frame reassembly failed (-84)" on every cold boot.

In `drivers/tty/serial/qcom_geni_serial.c`, find `qcom_geni_serial_handle_rx_dma()`:

```diff
-    if (!rx_in) {
-        return;
-    }
-    handle_rx_uart(uport, rx_in, drop);
+    if (rx_in)
+        handle_rx_uart(uport, rx_in, drop);
+
     geni_se_rx_dma_prep(se, port->rx_buf, DMA_RX_BUF_SIZE,
                         &port->rx_dma_addr);
```

Rebuild the kernel. This makes BT firmware download reliable on all boot types.

---

## 5. Fix the all-zero BD_ADDR (HCI_UNCONFIGURED)

`crnv21.bin` ships with BD_ADDR `00:00:00:00:00:00`. The kernel reads this
during BT init and marks hci0 `HCI_UNCONFIGURED`. `HCIDEVUP` returns `EOPNOTSUPP`.

Fix: send `MGMT_OP_SET_PUBLIC_ADDRESS (0x0039)` via the BlueZ management socket.
This is the only management command that works on unconfigured devices.

```bash
# With btmgmt:
btmgmt public-addr 00:17:F2:xx:xx:xx

# Or compile and run the static binary from tools/hci-mgmt.c
aarch64-linux-gnu-gcc -static -o hci-mgmt hci-mgmt.c
./hci-mgmt 0
```

**The write is permanent:** `qca_set_bdaddr()` sends `EDL_WRITE_BD_ADDR_OPCODE`
which writes to WCN3990 NVM storage. After the next reboot, the chip loads the
updated NVM, the kernel reads a valid BD_ADDR, and hci0 comes UP automatically
without any userspace intervention. You only need to do this once.

After the NVM write, hci0 auto-powers at boot:
```
Bluetooth: hci0: QCA setup on UART is completed
```
And `HCIDEVUP` returns `EALREADY` (already UP).

---

## 6. Start bluetoothd

Our Buildroot rootfs had `bluetoothd 5.72` and `S30dbus`/`S40bluetoothd` init
scripts already present. The only missing piece was the `dbus` system user:

```bash
echo 'dbus:x:81:81:System message bus:/run/dbus:/bin/false' >> /etc/passwd
echo 'dbus:x:81:' >> /etc/group
mkdir -p /etc/bluetooth
printf '[Policy]\nAutoEnable=true\n' > /etc/bluetooth/main.conf
/etc/init.d/S30dbus start
/etc/init.d/S40bluetoothd start
```

After bluetoothd starts:
```
BD_ADDR:            00:17:F2:AA:BB:CC
Version:            0x09  (Bluetooth 5.0)
Manufacturer:       0x001d (Qualcomm)
Current settings:   POWERED SSP BREDR LE (0x00000ac1)
```

"Failed to set privacy: Rejected (0x0b)" is expected — WCN3990 on SM8150 does
not support LE privacy address rotation in this configuration. Not a blocker.

---

## 7. Reading controller info in kernel 6.11

Kernel 6.11 removed HCI sysfs attributes (`address`, `name`, `type`).
`/sys/class/bluetooth/hci0/` only contains kobject basics. Use the management
socket instead:

```bash
btmgmt info       # if available
bluetoothctl show # if available
```

Or use `MGMT_OP_READ_INFO (0x0004)`. The `mgmt_rp_read_info` struct field order
in kernel 6.11 is: `bdaddr, version, manufacturer, supported_settings,
current_settings, dev_class, name, short_name` — note that `manufacturer` comes
before the settings fields, and settings come before `dev_class`/`name`. Older
documentation shows a different layout.

---

## Summary of what persists across reboots

| Item | Persistence | How |
|------|-------------|-----|
| BD_ADDR | Permanent | Written to WCN3990 NVM by `qca_set_bdaddr()` |
| dbus user | Persistent | Written to `/etc/passwd` on ext4 rootfs |
| bluetooth config | Persistent | `/etc/bluetooth/main.conf` on ext4 |
| init scripts | Already present | `S30dbus`, `S40bluetoothd` from Buildroot |
| GENI DMA fix | Persistent | Kernel patch, rebuilt binary |

---

## Tools

- `tools/hci-mgmt.c` — set BD_ADDR via MGMT socket (run once, NVM write)
- `tools/hci-info.c` — read controller info via MGMT READ_INFO
- `tools/hci-up.c` — bring up hci0 via HCIDEVUP ioctl + read BD_ADDR
- `tools/patch-geni-uart-dma.py` — applies the GENI DMA fix to kernel source
