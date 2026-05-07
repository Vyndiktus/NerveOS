# WCN3990 Bluetooth firmware on SDM845/SM8150: symlink crnv21→crnv01

**Hardware:** Qualcomm WCN3990 combo WiFi+BT  
**SoCs:** SDM845 (Snapdragon 845), SM8150 (Snapdragon 855)  
**Symptom:** `hci0: Direct firmware load for qca/crnv01.bin failed with error -2`

---

## Background

The QCA UART BT driver (`drivers/bluetooth/btqca.c`) requests firmware files
based on the controller version reported by the chip. The file name format is:

```
qca/crbtfw%02x.tlv   ← patch firmware (ROM patches)
qca/crnv%02x.bin     ← NVM (config: BD_ADDR, crystal freq, RF calibration)
```

Where `%02x` is the version byte from the `QCA_GET_TARGET_VERSION` response.

WCN3990 as found on SM8150 typically reports version `0x01`, requesting:
- `qca/crbtfw01.tlv`
- `qca/crnv01.bin`

The firmware files in `linux-firmware.git` are named for the SDM845 variant:
- `qca/crbtfw21.tlv`
- `qca/crnv21.bin`

---

## The fix

Create symlinks so the SM8150 version request finds the SDM845 firmware files:

```bash
cd /lib/firmware/qca
ln -sf crbtfw21.tlv crbtfw01.tlv
ln -sf crnv21.bin   crnv01.bin
```

After rebooting or re-probing the driver:
```
Bluetooth: hci0: QCA Patch Version:0x00006699
Bluetooth: hci0: QCA controller version 0x02241001
Bluetooth: hci0: QCA Downloading qca/crbtfw01.tlv
Bluetooth: hci0: QCA Downloading qca/crnv01.bin
Bluetooth: hci0: QCA setup on UART is completed
```

---

## Why the version differs

The WCN3990 silicon is the same chip used in SDM845 and SM8150 devices, but
the firmware version byte reported varies by the ROM version burned into the
chip at manufacturing time. SM8150 production units and SDM845 units have
slightly different ROM versions that cause the driver to request different
version numbers, but the actual firmware content (`crnv21.bin`) is compatible
with both.

---

## Firmware source

From `linux-firmware.git` (or distribution packages):
```
qca/crbtfw21.tlv   — WCN3990 BT patch firmware
qca/crnv21.bin     — WCN3990 NVM (contains BD_ADDR = 00:00:00:00:00:00 on stock)
```

Note: `crnv21.bin` ships with an all-zero BD_ADDR. On SM8150/SDM845 this causes
the kernel to mark the device `HCI_UNCONFIGURED`. See the companion write-up on
fixing that.

---

## Alternative: check the version your chip reports

Enable BT debug and watch dmesg during firmware load to see exactly which version
your chip reports:

```bash
echo 'module btqca +p' > /sys/kernel/debug/dynamic_debug/control
# (trigger BT probe)
dmesg | grep -i 'qca\|crbtfw\|crnv'
```

The log line `QCA Downloading qca/crbtfw01.tlv` tells you which symlink to create.

---

## Confirmed working

- SM8150 (cepheus / Xiaomi Mi 9): `crbtfw01.tlv → crbtfw21.tlv`, `crnv01.bin → crnv21.bin`
- Controller version after firmware load: `0x02241001`
- Patch version: `0x00006699`
