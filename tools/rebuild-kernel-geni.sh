#!/bin/bash
set -e
K=/opt/NerveOS/build/cepheus/build/linux-4a8d88483

echo "Recompiling qcom_geni_serial.o..."
make -C $K ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- \
  drivers/tty/serial/qcom_geni_serial.o 2>&1 | tail -3

echo "Rebuilding vmlinux + Image..."
make -C $K ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- \
  Image 2>&1 | tail -5

echo "Compressing..."
gzip -9 -c $K/arch/arm64/boot/Image > /tmp/Image_geni_fix.gz
ls -lh /tmp/Image_geni_fix.gz
echo "Done."
