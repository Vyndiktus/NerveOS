#!/bin/bash
CFG=/opt/NerveOS/build/cepheus/build/linux-cepheus-q-oss/.config
echo "=== USB Serial ==="
grep -E "USB_G_SERIAL|USB_CONFIGFS_SERIAL|USB_CONFIGFS_ACM" $CFG
echo "=== Clock drivers ==="
grep -E "^CONFIG_(CLK_SM8150|MSM_GCC|QCOM_CLK|CLK_QCOM)" $CFG | head -10
echo "=== DWC3 USB ==="
grep -E "^CONFIG_(USB_DWC3|USB_QCOM)" $CFG | head -5
echo "=== QCOM power ==="
grep -E "^CONFIG_(QCOM_RPMH|QCOM_COMMAND_DB|QCOM_GENI_SE)" $CFG | head -10
echo "=== Standalone cepheus DTS files ==="
ls /opt/NerveOS/build/cepheus/build/linux-cepheus-q-oss/arch/arm64/boot/dts/qcom/cepheus*.dts 2>/dev/null
ls /opt/NerveOS/build/cepheus/build/linux-cepheus-q-oss/arch/arm64/boot/dts/qcom/cepheus*.dtb 2>/dev/null
echo "=== SM8150 DTBs in kernel ==="
ls /opt/NerveOS/build/cepheus/build/linux-cepheus-q-oss/arch/arm64/boot/dts/qcom/sm8150*.dtb 2>/dev/null
