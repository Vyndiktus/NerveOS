#!/bin/bash
set -e
K=/opt/NerveOS/build/cepheus/build/linux-4a8d88483
DTS=$K/arch/arm64/boot/dts/qcom/sm8150-xiaomi-cepheus.dts
DTB=$K/arch/arm64/boot/dts/qcom/sm8150-xiaomi-cepheus.dtb

echo "Rebuilding DTB with BT pinctrl fix..."
cpp -nostdinc -undef -D__DTS__ -x assembler-with-cpp \
  -I $K/include -I $K/arch/arm64/boot/dts -I $K/arch/arm64/boot/dts/qcom \
  -o /tmp/cepheus_bt.dts.tmp $DTS

/usr/bin/dtc -O dtb -b 0 -W no-unit_address_vs_reg \
  -i $K/arch/arm64/boot/dts/qcom -i $K/arch/arm64/boot/dts \
  -o $DTB /tmp/cepheus_bt.dts.tmp 2>&1

echo "DTB size: $(stat -c %s $DTB) bytes"
echo "DTB mtime: $(stat -c %y $DTB)"
echo "Done."
