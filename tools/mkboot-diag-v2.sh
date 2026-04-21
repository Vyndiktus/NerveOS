#!/bin/bash
set -e
cd /opt/hiveos/build/cepheus/build/linux-4a8d88483
cat arch/arm64/boot/Image.gz arch/arm64/boot/dts/qcom/sm8150-xiaomi-cepheus.dtb > /tmp/Image-with-dtb.gz
echo "Kernel+DTB: $(ls -lh /tmp/Image-with-dtb.gz)"

mkbootimg \
  --kernel /tmp/Image-with-dtb.gz \
  --ramdisk /opt/hiveos-pcsfix90-initrd.gz \
  --cmdline "nomodeset clk_ignore_unused pd_ignore_unused console=tty0 console=ttyMSM0,115200n8 earlycon=qcom_geni,0xa90000 loglevel=8 rdinit=/init" \
  --header_version 1 \
  --pagesize 4096 \
  --base 0x00000000 \
  --kernel_offset 0x00008000 \
  --ramdisk_offset 0x01000000 \
  --tags_offset 0x00000100 \
  --output /opt/boot_diag_v2.img

echo "Boot image: $(ls -lh /opt/boot_diag_v2.img)"
cp /opt/boot_diag_v2.img "/mnt/c/Windows/Temp/boot_diag_v2.img"
echo "Copied to Windows"
