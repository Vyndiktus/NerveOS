#!/bin/bash
K=/opt/NerveOS/build/cepheus/build/linux-cepheus-q-oss

echo "=== USB serial Kconfig file location ==="
find $K/drivers/usb -name "Kconfig" | xargs grep -l "CONFIGFS_SERIAL\|G_SERIAL" 2>/dev/null

echo "=== Full USB_CONFIGFS_SERIAL Kconfig block ==="
for f in $(find $K/drivers/usb -name "Kconfig"); do
    if grep -q "CONFIGFS_SERIAL" $f 2>/dev/null; then
        echo "--- $f ---"
        grep -B2 -A15 "config USB_CONFIGFS_SERIAL" $f
    fi
done

echo "=== Check if USB_CONFIGFS_F_SERIAL exists ==="
find $K/drivers/usb -name "f_serial*" -o -name "u_serial*" 2>/dev/null | head -5

echo "=== sm8150-v2 reserved-memory section ==="
sed -n '590,650p' $K/arch/arm64/boot/dts/qcom/sm8150-v2.dts 2>/dev/null
