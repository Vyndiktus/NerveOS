#!/bin/bash
set -e
K=/opt/NerveOS/build/cepheus/build/linux-4a8d88483

echo "Rebuilding btqca.ko..."
make -C $K M=$K/drivers/bluetooth \
  ARCH=arm64 \
  CROSS_COMPILE=aarch64-linux-gnu- \
  CONFIG_BT=m \
  CONFIG_BT_QCA=m \
  CONFIG_BT_HCIUART=m \
  CONFIG_BT_HCIUART_QCA=y \
  CONFIG_BT_BCM=m \
  btqca.o 2>&1 | tail -5

# Link btqca.ko
make -C $K M=$K/drivers/bluetooth \
  ARCH=arm64 \
  CROSS_COMPILE=aarch64-linux-gnu- \
  btqca.ko 2>&1 | tail -10

ls -lh $K/drivers/bluetooth/btqca.ko
echo "Done."
