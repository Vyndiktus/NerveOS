#!/usr/bin/env python3
"""Patch qcom_geni_serial.c: re-arm DMA even when 0 RX bytes reported."""

GENI = "/opt/NerveOS/build/cepheus/build/linux-4a8d88483/drivers/tty/serial/qcom_geni_serial.c"

with open(GENI) as f:
    content = f.read()

old = '''\trx_in = readl(uport->membase + SE_DMA_RX_LEN_IN);
\tif (!rx_in) {
\t\tdev_warn(uport->dev, "serial engine reports 0 RX bytes in!\\n");
\t\treturn;
\t}

\tif (!drop)
\t\thandle_rx_uart(uport, rx_in, drop);

\tret = geni_se_rx_dma_prep(&port->se, port->rx_buf,
\t\t\t\t  DMA_RX_BUF_SIZE,
\t\t\t\t  &port->rx_dma_addr);'''

new = '''\trx_in = readl(uport->membase + SE_DMA_RX_LEN_IN);
\tif (!rx_in) {
\t\tdev_warn(uport->dev, "serial engine reports 0 RX bytes in!\\n");
\t\t/* Do NOT return here — re-arm DMA so future RX still works */
\t} else if (!drop) {
\t\thandle_rx_uart(uport, rx_in, drop);
\t}

\tret = geni_se_rx_dma_prep(&port->se, port->rx_buf,
\t\t\t\t  DMA_RX_BUF_SIZE,
\t\t\t\t  &port->rx_dma_addr);'''

if old in content:
    content = content.replace(old, new, 1)
    with open(GENI, "w") as f:
        f.write(content)
    print("qcom_geni_serial.c patched: DMA re-armed even after 0-byte spurious interrupt")
else:
    print("ERROR: pattern not found — showing context:")
    idx = content.find("serial engine reports 0 RX bytes in")
    if idx >= 0:
        print(repr(content[max(0, idx-200):idx+400]))
    import sys; sys.exit(1)
