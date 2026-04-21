#!/bin/bash
K=/opt/NerveOS/build/cepheus/build/linux-cepheus-q-oss

echo "=== cepheus_user_defconfig USB serial ==="
grep -E "USB_CONFIGFS_SERIAL|USB_G_SERIAL|USB_U_SERIAL|USB_F_SERIAL|USB_F_ACM" \
    $K/arch/arm64/configs/cepheus_user_defconfig 2>/dev/null

echo "=== Any arch/arm64 defconfig with SERIAL disabled ==="
grep "USB_CONFIGFS_SERIAL" $K/arch/arm64/configs/*.defconfig 2>/dev/null | head -10

echo "=== Current .config value ==="
grep -E "USB_CONFIGFS_SERIAL|USB_U_SERIAL|USB_F_SERIAL" $K/.config

echo "=== Force-set and test olddefconfig ==="
# Save backup
cp $K/.config $K/.config.bak

# Force set
sed -i 's/# CONFIG_USB_CONFIGFS_SERIAL is not set/CONFIG_USB_CONFIGFS_SERIAL=y/' $K/.config
echo "CONFIG_USB_U_SERIAL=y" >> $K/.config
echo "CONFIG_USB_F_SERIAL=y" >> $K/.config

echo "After sed, before olddefconfig:"
grep -E "USB_CONFIGFS_SERIAL|USB_U_SERIAL|USB_F_SERIAL" $K/.config

# Run olddefconfig
cd $K && make olddefconfig ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- 2>&1 | tail -5

echo "After olddefconfig:"
grep -E "USB_CONFIGFS_SERIAL|USB_U_SERIAL|USB_F_SERIAL" $K/.config
