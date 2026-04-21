#!/bin/bash
CFG=/opt/NerveOS/build/cepheus/build/linux-cepheus-q-oss/.config
K=/opt/NerveOS/build/cepheus/build/linux-cepheus-q-oss

echo "=== TTY config ==="
grep "^CONFIG_TTY" $CFG

echo "=== USB_F_SERIAL / USB_U_SERIAL ==="
grep -E "^CONFIG_(USB_F_SERIAL|USB_U_SERIAL|USB_F_ACM)" $CFG

echo "=== Boot reason / panic reason ==="
grep -E "^CONFIG_(POWER_RESET|QCOM_DLOAD|PANIC|QCOM_WATCHDOG_V2)" $CFG | head -10

echo "=== How fast is the boot loop? ==="
echo "Try timing: fastboot reboot, then check how long before back in fastboot"
date

echo "=== sm8150-v2 reserved memory nodes ==="
grep -n "ramoops\|oops\|mem_address\|mem_size\|reserved" $K/arch/arm64/boot/dts/qcom/sm8150-v2.dts | head -30

echo "=== APQ8016 ramoops reference ==="
grep -A10 "ramoops@" $K/arch/arm64/boot/dts/qcom/apq8016-sbc.dtsi | head -20
