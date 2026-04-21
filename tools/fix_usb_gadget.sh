#!/bin/bash
set -e
K=/opt/NerveOS/build/cepheus/build/linux-cepheus-q-oss
export ARCH=arm64
export CROSS_COMPILE=aarch64-linux-gnu-
export PATH=/opt/NerveOS/build/cepheus/host/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

echo "=== Current USB gadget state ==="
grep -E "^CONFIG_(USB_G_SERIAL|USB_CONFIGFS_SERIAL|USB_CONFIGFS_ACM|USB_U_SERIAL|USB_F_SERIAL|USB_F_ACM)" $K/.config

echo "=== Disabling USB_G_SERIAL (conflicts with DWC3_MSM configfs gadget) ==="
# Remove USB_G_SERIAL - it tries to bind to UDC immediately and conflicts with DWC3_MSM
sed -i 's/^CONFIG_USB_G_SERIAL=y/# CONFIG_USB_G_SERIAL is not set/' $K/.config

# Keep USB_CONFIGFS_SERIAL and ACM (configured via configfs by userspace)
echo "After edit:"
grep -E "^CONFIG_(USB_G_SERIAL|USB_CONFIGFS_SERIAL|USB_CONFIGFS_ACM)" $K/.config
grep "USB_G_SERIAL" $K/.config

cd $K && make olddefconfig 2>&1 | tail -3

echo "After olddefconfig:"
grep -E "USB_G_SERIAL|USB_CONFIGFS_SERIAL|USB_CONFIGFS_ACM|USB_U_SERIAL|USB_F_SERIAL" $K/.config

echo "=== Touching USB gadget file to force rebuild ==="
touch $K/drivers/usb/gadget/function/f_serial.c

echo "=== Rebuilding kernel Image ==="
make -j$(nproc) Image 2>&1 | tail -10

echo "=== Done ==="
ls -lh $K/arch/arm64/boot/Image
