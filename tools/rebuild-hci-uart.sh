#!/bin/bash
set -e
K=/opt/NerveOS/build/cepheus/build/linux-4a8d88483

echo "Rebuilding hci_uart.ko..."
make -C $K M=$K/drivers/bluetooth \
  ARCH=arm64 \
  CROSS_COMPILE=aarch64-linux-gnu- \
  CONFIG_BT=m \
  CONFIG_BT_QCA=m \
  CONFIG_BT_HCIUART=m \
  CONFIG_BT_HCIUART_QCA=y \
  CONFIG_BT_BCM=m \
  hci_uart.ko 2>&1 | tail -10

ls -lh $K/drivers/bluetooth/hci_uart.ko
echo "Done."
