#!/bin/bash
set -e
K=/opt/NerveOS/build/cepheus/build/linux-4a8d88483
DTB=$K/arch/arm64/boot/dts/qcom/sm8150-xiaomi-cepheus.dtb
IMAGE_GZ=/tmp/Image_geni_fix.gz

echo "Rebuilding DTB..."
cpp -nostdinc -undef -D__DTS__ -x assembler-with-cpp \
  -I $K/include -I $K/arch/arm64/boot/dts -I $K/arch/arm64/boot/dts/qcom \
  -o /tmp/cepheus_geni.dts.tmp \
  $K/arch/arm64/boot/dts/qcom/sm8150-xiaomi-cepheus.dts

/usr/bin/dtc -O dtb -b 0 -W no-unit_address_vs_reg \
  -i $K/arch/arm64/boot/dts/qcom -i $K/arch/arm64/boot/dts \
  -o $DTB /tmp/cepheus_geni.dts.tmp
ls -lh $DTB

echo "Concatenating kernel + DTB..."
cat $IMAGE_GZ $DTB > /tmp/kernel_geni_with_dtb.gz
ls -lh /tmp/kernel_geni_with_dtb.gz

echo "Building boot image..."
# Extract ramdisk from v37 boot image for reuse
python3 - <<'PYEOF'
import struct, sys

with open('/opt/boot_nerveos_v37.img', 'rb') as f:
    data = f.read()

# Parse Android boot image v0 header
magic = data[:8]
assert magic == b'ANDROID!', f"Bad magic: {magic}"

kernel_size = struct.unpack_from('<I', data, 8)[0]
ramdisk_size = struct.unpack_from('<I', data, 16)[0]
page_size = struct.unpack_from('<I', data, 36)[0]

def pages(n, ps): return (n + ps - 1) // ps

kernel_offset = page_size
ramdisk_offset = kernel_offset + pages(kernel_size, page_size) * page_size

with open('/tmp/v37_ramdisk.img', 'wb') as f:
    f.write(data[ramdisk_offset:ramdisk_offset + ramdisk_size])

print(f"Extracted ramdisk: {ramdisk_size} bytes")
print(f"Page size: {page_size}")
print(f"Original kernel size: {kernel_size}")
PYEOF

ls -lh /tmp/v37_ramdisk.img

CMDLINE="nomodeset clk_ignore_unused pd_ignore_unused console=tty0 console=ttyMSM0,115200n8 earlycon=qcom_geni,0xa90000 loglevel=8 rdinit=/init"

mkbootimg \
  --kernel /tmp/kernel_geni_with_dtb.gz \
  --ramdisk /tmp/v37_ramdisk.img \
  --cmdline "$CMDLINE" \
  --base 0x80000000 \
  --pagesize 4096 \
  --kernel_offset 0x00008000 \
  --ramdisk_offset 0x01000000 \
  --tags_offset 0x00000100 \
  -o /opt/boot_geni_fix.img

ls -lh /opt/boot_geni_fix.img
echo "Done."
