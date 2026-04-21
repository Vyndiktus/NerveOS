#!/bin/bash
IMG=/opt/hiveos/build/cepheus/build/linux-4a8d88483/arch/arm64/boot/Image.gz
DTB=/opt/hiveos/build/cepheus/build/linux-4a8d88483/arch/arm64/boot/dts/qcom/sm8150-xiaomi-cepheus.dtb
RAMDISK=/tmp/ramdisk.cpio.gz
OUT=/opt/nerveos-boot-noptimer.img

echo "IMG: $(ls -la $IMG)"
echo "DTB: $(ls -la $DTB)"

cat "$IMG" "$DTB" > /tmp/kernel-dtb.gz
echo "kernel-dtb.gz: $(stat -c%s /tmp/kernel-dtb.gz) bytes"

mkbootimg \
  --kernel /tmp/kernel-dtb.gz \
  --ramdisk "$RAMDISK" \
  --cmdline 'nomodeset clk_ignore_unused pd_ignore_unused console=tty0 console=ttyMSM0,115200n8 earlycon=qcom_geni,0xa90000 loglevel=8 rdinit=/init' \
  --base 0x00000000 \
  --kernel_offset 0x00008000 \
  --ramdisk_offset 0x02000000 \
  --tags_offset 0x00000100 \
  --pagesize 4096 \
  -o "$OUT" && echo MKBOOTIMG_OK

cp "$OUT" /mnt/c/Windows/Temp/NerveOS_boot_noptimer.img && echo COPIED
