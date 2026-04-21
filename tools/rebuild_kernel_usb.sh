#!/bin/bash
set -e
K=/opt/NerveOS/build/cepheus/build/linux-cepheus-q-oss
export PATH=/opt/NerveOS/build/cepheus/host/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export ARCH=arm64
export CROSS_COMPILE=aarch64-linux-gnu-

echo "=== Verifying USB serial in config ==="
grep -E "USB_CONFIGFS_SERIAL|USB_U_SERIAL|USB_F_SERIAL" $K/.config

echo "=== Touching modified file to force rebuild ==="
touch $K/drivers/usb/gadget/function/f_serial.c

echo "=== Rebuilding kernel Image ==="
cd $K
make -j$(nproc) Image 2>&1 | tail -10

echo "=== Image built: ==="
ls -lh $K/arch/arm64/boot/Image
