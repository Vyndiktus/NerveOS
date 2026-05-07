# SM8150 GENI UART: BT RX dead after spurious DMA interrupt on cold boot

**Hardware:** Qualcomm SM8150 (Snapdragon 855), GENI serial engine (c8c000.serial)  
**Kernel:** mainline 6.11  
**Driver:** `drivers/tty/serial/qcom_geni_serial.c`  
**Symptom:** Bluetooth works on first boot after flash, fails on subsequent cold boots
with "Frame reassembly failed (-84)" and HCI command timeouts

---

## The symptom

After flashing a fresh kernel+rootfs, Bluetooth initialises correctly on the first
boot:
```
Bluetooth: hci0: QCA setup on UART is completed
```

On subsequent cold boots, firmware download starts but RX stops responding:
```
Bluetooth: hci0: Frame reassembly failed (-84)
Bluetooth: hci0: 0xfc00 tx timeout
```

`-84 = -EILSEQ` (Illegal byte sequence in the reassembler). The UART receives
garbage or nothing after the first few bytes of the firmware download.

A warm reboot (not a full power cycle) may work intermittently.

---

## Root cause

In `qcom_geni_serial_handle_rx_dma()`, there is an early return when
`SE_DMA_RX_LEN_IN = 0`:

```c
static void qcom_geni_serial_handle_rx_dma(struct uart_port *uport, ...)
{
    struct qcom_geni_serial_port *port = ...;
    u32 rx_in = readl_relaxed(uport->membase + SE_DMA_RX_LEN_IN);

    if (!rx_in) {
        /* Spurious DMA interrupt — but we return without re-arming! */
        return;   /* ← BUG */
    }

    handle_rx_uart(uport, rx_in, drop);
    geni_se_rx_dma_prep(...);   /* re-arm for next transfer */
}
```

On cold boot, chip startup noise produces a spurious DMA interrupt with
`SE_DMA_RX_LEN_IN = 0`. The early `return` skips `geni_se_rx_dma_prep()` — the
call that re-arms the DMA for the next receive. After this, the UART's DMA RX
descriptor is never re-armed, so all subsequent received bytes are silently dropped.
The GENI hardware has no automatic re-arm on DMA completion.

The spurious interrupt only occurs on cold boots (hardware startup transient),
which is why the bug only manifests on power-cycle reboots.

---

## The fix

Re-arm the DMA unconditionally. Only skip the data processing when `rx_in == 0`:

```c
static void qcom_geni_serial_handle_rx_dma(struct uart_port *uport, ...)
{
    struct qcom_geni_serial_port *port = ...;
    u32 rx_in = readl_relaxed(uport->membase + SE_DMA_RX_LEN_IN);

    if (rx_in)
        handle_rx_uart(uport, rx_in, drop);

    /* Re-arm DMA regardless — never leave the descriptor unqueued */
    geni_se_rx_dma_prep(se, port->rx_buf, DMA_RX_BUF_SIZE,
                        &port->rx_dma_addr);
}
```

This ensures the DMA descriptor is always re-armed after any interrupt, whether
or not data was actually received.

---

## Patch (against mainline 6.11)

```diff
--- a/drivers/tty/serial/qcom_geni_serial.c
+++ b/drivers/tty/serial/qcom_geni_serial.c
@@ -xxx,10 +xxx,11 @@ static void qcom_geni_serial_handle_rx_dma(struct uart_port *uport,
 	u32 rx_in = readl_relaxed(uport->membase + SE_DMA_RX_LEN_IN);
 
-	if (!rx_in) {
-		dev_dbg(uport->dev, "Spurious RX DMA IRQ\n");
-		return;
-	}
+	if (rx_in)
+		handle_rx_uart(uport, rx_in, drop);
 
-	handle_rx_uart(uport, rx_in, drop);
 	geni_se_rx_dma_prep(se, port->rx_buf, DMA_RX_BUF_SIZE,
 			    &port->rx_dma_addr);
```

*(Exact line numbers depend on kernel version — search for `SE_DMA_RX_LEN_IN` in
`qcom_geni_serial_handle_rx_dma`.)*

---

## Verification

After patching, both cold boots and warm reboots produce:
```
Bluetooth: hci0: QCA Downloading qca/crbtfw01.tlv
Bluetooth: hci0: QCA Downloading qca/crnv01.bin
Bluetooth: hci0: QCA setup on UART is completed
```
consistently, with no "Frame reassembly failed" errors.

---

## Affected hardware

Any device using:
- Qualcomm GENI serial engine in DMA mode
- A BT UART device on that port (WCN3990, WCN3980, WCN6750, etc.)
- Cold boot with hardware startup transients on the UART lines

Confirmed on SM8150 (Snapdragon 855). The same GENI serial IP block appears across
SDM845, SM8150, SM8250, SM8350 and many other Snapdragon SoCs, so this likely
affects all of them.

---

## Why it's intermittent without the fix

The spurious DMA interrupt only occurs during the UART's power-on transient. On
warm reboots the UART is already powered and stable, so no spurious interrupt fires
and the DMA stays armed. This makes the bug appear as "BT works after `fastboot
boot` but not after a real reboot" — exactly the pattern that makes it hard to
diagnose.
