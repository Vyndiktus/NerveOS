#!/bin/bash
set -e
K=/opt/NerveOS/build/cepheus/build/linux-cepheus-q-oss
DTS=$K/arch/arm64/boot/dts/qcom

echo "=== Step 1: Preprocess cepheus overlay DTS ==="
cpp -nostdinc -undef -x assembler-with-cpp \
    -I$DTS \
    -I$K/include \
    $DTS/cepheus-sm8150-overlay.dts \
    -o /opt/cepheus-pp.dts
echo "cpp done"

echo "=== Step 2: Compile overlay to dtbo ==="
dtc -@ -I dts -O dtb /opt/cepheus-pp.dts -o /opt/cepheus.dtbo 2>&1 | grep -v Warning | head -3
echo "dtc done: $(ls -lh /opt/cepheus.dtbo)"

echo "=== Step 3: Copy base DTB (ABL applies cepheus overlay from dtbo partition) ==="
cp $DTS/sm8150-v2.dtb /opt/base.dtb
echo "base dtb: $(ls -lh /opt/base.dtb)"

echo "=== Step 4: Build boot image ==="
echo -n | gzip > /opt/empty.gz
mkbootimg \
  --kernel $K/arch/arm64/boot/Image \
  --ramdisk /opt/empty.gz \
  --dtb /opt/base.dtb \
  --cmdline "console=ttyMSM0,115200n8 console=ttyGS0,115200 earlycon=msm_geni_serial,0xa90000 androidboot.hardware=qcom androidboot.bootdevice=1d84000.ufshc root=PARTLABEL=system rootwait rw loglevel=8" \
  --header_version 2 \
  --pagesize 4096 \
  --base 0x00000000 \
  --kernel_offset 0x00008000 \
  --ramdisk_offset 0x01000000 \
  --tags_offset 0x00000100 \
  --dtb_offset 0x01f00000 \
  --output /opt/boot_cepheus.img

echo "Done: $(ls -lh /opt/boot_cepheus.img)"
cp /opt/boot_cepheus.img "/mnt/c/Windows/Temp/NerveOS_boot_cepheus.img"
echo "Copied to Windows temp"
