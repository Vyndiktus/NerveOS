#!/bin/bash
set -e
BOOT=/mnt/c/Windows/Temp/miui_boot.img

echo "=== Extracting stock kernel blob from MIUI boot.img ==="
python3 << 'PYEOF'
import struct, sys

with open('/mnt/c/Windows/Temp/miui_boot.img', 'rb') as f:
    hdr = f.read(1648)

page_size, = struct.unpack_from('<I', hdr, 36)
kernel_size, = struct.unpack_from('<I', hdr, 8)
ramdisk_size, = struct.unpack_from('<I', hdr, 16)
second_size, = struct.unpack_from('<I', hdr, 24)
header_version, = struct.unpack_from('<I', hdr, 40)

kernel_offset = page_size  # after 1 page header
print(f'Extracting kernel: offset={kernel_offset} size={kernel_size} ({kernel_size/1024/1024:.1f} MB)')

with open('/mnt/c/Windows/Temp/miui_boot.img', 'rb') as f:
    f.seek(kernel_offset)
    kernel = f.read(kernel_size)

with open('/opt/miui-kernel-blob', 'wb') as f:
    f.write(kernel)
print(f'Saved to /opt/miui-kernel-blob')

# Check if it ends with a DTB
# Search for FDT magic 0xd00dfeed near the end
magic_bytes = struct.pack('>I', 0xd00dfeed)
idx = kernel.rfind(magic_bytes)
if idx >= 0:
    print(f'FDT magic found at offset {idx} ({idx/1024/1024:.1f} MB into kernel blob)')
    # Read DTB size from FDT header
    dtb_size, = struct.unpack_from('>I', kernel, idx+4)
    print(f'DTB size at that offset: {dtb_size} bytes')
PYEOF

ls -lh /opt/miui-kernel-blob

echo "=== Building test boot image: stock kernel + our debug initramfs ==="
mkbootimg \
  --kernel /opt/miui-kernel-blob \
  --ramdisk /opt/NerveOS-debug-initrd.gz \
  --cmdline "console=ttyMSM0,115200n8 console=ttyGS0,115200 earlycon=msm_geni_serial,0xa90000 androidboot.hardware=qcom lpm_levels.sleep_disabled=1 swiotlb=2048 androidboot.usbcontroller=a600000.dwc3 service_locator.enable=1 androidboot.bootdevice=1d84000.ufshc loglevel=8 rdinit=/init" \
  --header_version 1 \
  --pagesize 4096 \
  --base 0x00000000 \
  --kernel_offset 0x00008000 \
  --ramdisk_offset 0x01000000 \
  --tags_offset 0x00000100 \
  --output /opt/boot_stock_kernel_debug.img

echo "Done: $(ls -lh /opt/boot_stock_kernel_debug.img)"
cp /opt/boot_stock_kernel_debug.img "/mnt/c/Windows/Temp/NerveOS_stock_kernel_debug.img"
echo "Copied to Windows temp"
