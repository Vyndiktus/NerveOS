#!/bin/bash
K=/opt/NerveOS/build/cepheus/build/linux-cepheus-q-oss
DTS=$K/arch/arm64/boot/dts/qcom

echo "=== USB_CONFIGFS_SERIAL Kconfig deps ==="
grep -A10 "config USB_CONFIGFS_SERIAL" $K/drivers/usb/gadget/function/Kconfig 2>/dev/null

echo "=== USB_G_SERIAL Kconfig ==="
grep -B2 -A10 "config USB_G_SERIAL" $K/drivers/usb/gadget/Kconfig 2>/dev/null

echo "=== ramoops in ALL sm8150 DTS ==="
grep -r "ramoops" $DTS/ 2>/dev/null | head -20

echo "=== reserved-memory in sm8150-v2.dts ==="
grep -n "reserved-memory\|ramoops\|oops\|pstore" $DTS/sm8150-v2.dts 2>/dev/null | head -20
grep -n "reserved-memory\|ramoops\|oops\|pstore" $DTS/sm8150.dtsi 2>/dev/null | head -20
