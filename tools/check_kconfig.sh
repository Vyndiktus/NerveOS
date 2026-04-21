#!/bin/bash
CFG=/opt/NerveOS/build/cepheus/build/linux-cepheus-q-oss/.config
echo "=== Clock/Regulator/GPIO/Watchdog ==="
grep -E "^CONFIG_(CLK_QCOM|REGULATOR|SPMI|WATCHDOG|QCOM_WDT|MSM_GCC_8150|MSM_MMCC_8150)" $CFG
echo "=== GIC interrupt controller ==="
grep -E "^CONFIG_ARM_GIC" $CFG
echo "=== Pinctrl ==="
grep -E "^CONFIG_PINCTRL" $CFG | head -5
echo "=== USB gadget ==="
grep -E "^CONFIG_(USB_GADGET|USB_CONFIGFS|USB_G_SERIAL)" $CFG
echo "=== Randomize base ==="
grep "CONFIG_RANDOMIZE_BASE" $CFG
echo "=== Kallsyms ==="
grep "CONFIG_KALLSYMS_BASE_RELATIVE" $CFG
echo "=== pstore ==="
grep "CONFIG_PSTORE" $CFG
