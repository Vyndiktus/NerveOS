#!/bin/bash
K=/opt/NerveOS/build/cepheus/build/linux-cepheus-q-oss
DTS=$K/arch/arm64/boot/dts/qcom

echo "=== ramoops in overlay DTS ==="
grep -r "ramoops\|oops\|pstore\|mem_address\|mem_size" $DTS/cepheus-sm8150-overlay.dts 2>/dev/null | head -20

echo "=== ramoops in sm8150 base DTS ==="
grep -r "ramoops\|pstore" $DTS/sm8150.dtsi 2>/dev/null | head -20

echo "=== USB configfs serial Kconfig symbol ==="
grep -r "USB_CONFIGFS.*SERIAL\|USB_CONFIGFS.*ACM\|USB.*G_SERIAL" $K/drivers/usb/gadget/Kconfig 2>/dev/null | head -20
grep -r "USB_CONFIGFS.*SERIAL\|USB_CONFIGFS.*ACM\|USB.*G_SERIAL" $K/drivers/usb/gadget/function/Kconfig 2>/dev/null | head -20

echo "=== reserved memory in overlay ==="
grep -A5 "reserved-memory\|ramoops\|linux,contiguous" $DTS/cepheus-sm8150-overlay.dts 2>/dev/null | head -40
