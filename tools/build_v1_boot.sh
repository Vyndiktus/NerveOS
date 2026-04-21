#!/bin/bash
set -e
K=/opt/NerveOS/build/cepheus/build/linux-cepheus-q-oss
DTS=$K/arch/arm64/boot/dts/qcom

echo "=== Step 1: Compress kernel ==="
gzip -c $K/arch/arm64/boot/Image > /opt/Image.gz
echo "Image.gz: $(ls -lh /opt/Image.gz)"

echo "=== Step 2: Build Image.gz-dtb (kernel + base DTB concatenated) ==="
cat /opt/Image.gz $DTS/sm8150-v2.dtb > /opt/Image.gz-dtb
echo "Image.gz-dtb: $(ls -lh /opt/Image.gz-dtb)"

echo "=== Step 3: Build header v1 boot image with stock-compatible cmdline ==="
# Use EXACT stock cmdline params, plus our NerveOS root mount
# lpm_levels.sleep_disabled=1 is critical - prevents deep sleep hang during boot
mkbootimg \
  --kernel /opt/Image.gz-dtb \
  --ramdisk /opt/NerveOS-debug-initrd.gz \
  --cmdline "console=ttyMSM0,115200n8 console=ttyGS0,115200 earlycon=msm_geni_serial,0xa90000 androidboot.hardware=qcom androidboot.console=ttyMSM0 lpm_levels.sleep_disabled=1 androidboot.memcg=1 swiotlb=2048 loop.max_part=7 androidboot.usbcontroller=a600000.dwc3 msm_rtb.filter=0x237 service_locator.enable=1 androidboot.bootdevice=1d84000.ufshc loglevel=8 nosmp initcall_debug panic=3 softlockup_panic=1 watchdog_thresh=15 hung_task_panic=1 hung_task_timeout_secs=15 ramoops.mem_address=0xb0000000 ramoops.mem_size=0x400000 ramoops.console_size=0x200000 ramoops.record_size=0x200000 rdinit=/init" \
  --header_version 1 \
  --pagesize 4096 \
  --base 0x00000000 \
  --kernel_offset 0x00008000 \
  --ramdisk_offset 0x01000000 \
  --tags_offset 0x00000100 \
  --output /opt/boot_v1_debug.img

echo "Done: $(ls -lh /opt/boot_v1_debug.img)"
cp /opt/boot_v1_debug.img "/mnt/c/Windows/Temp/NerveOS_boot_v1_debug.img"
echo "Copied to Windows temp"
