#!/bin/bash
set -e
BOOT=/mnt/c/Windows/Temp/miui_boot.img
DTBO=/mnt/c/Windows/Temp/miui_dtbo.img
OUT=/opt/miui-boot-unpacked
mkdir -p $OUT

echo "=== Boot image header ==="
# Use mkbootimg tools to inspect
python3 -c "
import struct, sys
with open('$BOOT','rb') as f:
    magic = f.read(8)
    print('Magic:', magic)
    if magic == b'ANDROID!':
        f.seek(0)
        data = f.read(1648)
        # v2 header
        kernel_size, = struct.unpack_from('<I', data, 8)
        kernel_addr, = struct.unpack_from('<I', data, 12)
        ramdisk_size, = struct.unpack_from('<I', data, 16)
        ramdisk_addr, = struct.unpack_from('<I', data, 20)
        second_size, = struct.unpack_from('<I', data, 24)
        second_addr, = struct.unpack_from('<I', data, 28)
        tags_addr, = struct.unpack_from('<I', data, 32)
        page_size, = struct.unpack_from('<I', data, 36)
        header_version, = struct.unpack_from('<I', data, 40)
        os_version, = struct.unpack_from('<I', data, 44)
        cmdline = data[64:64+512].rstrip(b'\x00').decode('ascii','replace')
        extra_cmdline = data[608:608+1024].rstrip(b'\x00').decode('ascii','replace')
        print(f'Header version: {header_version}')
        print(f'Kernel size: {kernel_size} bytes ({kernel_size/1024/1024:.1f} MB)')
        print(f'Kernel addr: 0x{kernel_addr:08x}')
        print(f'Ramdisk size: {ramdisk_size} bytes')
        print(f'Page size: {page_size}')
        print(f'Tags addr: 0x{tags_addr:08x}')
        print(f'Cmdline: {cmdline}')
        print(f'Extra cmdline: {extra_cmdline}')
        if header_version >= 2:
            dtb_size, = struct.unpack_from('<I', data, 1632)
            dtb_addr, = struct.unpack_from('<Q', data, 1636)
            print(f'DTB size: {dtb_size} bytes ({dtb_size/1024:.1f} KB)')
            print(f'DTB addr: 0x{dtb_addr:016x}')
"

echo "=== Extracting components with unpackbootimg ==="
if command -v unpackbootimg >/dev/null 2>&1; then
    unpackbootimg -i $BOOT -o $OUT --format mkbootimg
else
    echo "unpackbootimg not found, using manual extraction"
fi

echo "=== Manual extraction of DTB ==="
python3 << 'PYEOF'
import struct, os

with open('/mnt/c/Windows/Temp/miui_boot.img', 'rb') as f:
    data = f.read(1648)

page_size, = struct.unpack_from('<I', data, 36)
kernel_size, = struct.unpack_from('<I', data, 8)
ramdisk_size, = struct.unpack_from('<I', data, 16)
second_size, = struct.unpack_from('<I', data, 24)
header_version, = struct.unpack_from('<I', data, 40)

def pages(n, page): return (n + page - 1) // page

hdr_pages = 1
kernel_pages = pages(kernel_size, page_size)
ramdisk_pages = pages(ramdisk_size, page_size)
second_pages = pages(second_size, page_size)

kernel_offset = hdr_pages * page_size
ramdisk_offset = kernel_offset + kernel_pages * page_size
second_offset = ramdisk_offset + ramdisk_pages * page_size

print(f'page_size={page_size}, header_version={header_version}')
print(f'kernel: offset={kernel_offset} size={kernel_size}')
print(f'ramdisk: offset={ramdisk_offset} size={ramdisk_size}')

if header_version >= 2:
    dtb_size, = struct.unpack_from('<I', data, 1632)
    dtb_addr, = struct.unpack_from('<Q', data, 1636)
    dtb_offset = second_offset + second_pages * page_size
    print(f'dtb: offset={dtb_offset} size={dtb_size} addr=0x{dtb_addr:x}')

    with open('/mnt/c/Windows/Temp/miui_boot.img', 'rb') as f:
        f.seek(dtb_offset)
        dtb_data = f.read(dtb_size)

    with open('/opt/miui-dtb.dtb', 'wb') as f:
        f.write(dtb_data)
    print(f'Saved DTB to /opt/miui-dtb.dtb ({len(dtb_data)} bytes)')

    # Check if it's a multi-DTB (QCOM DTBO table) or single DTB
    magic = struct.unpack_from('>I', dtb_data, 0)[0]
    print(f'DTB magic: 0x{magic:08x} (FDT magic is 0xd00dfeed, DTBO table magic is 0xd7b7ab1e)')
PYEOF

echo "=== Decompile extracted DTB ==="
if [ -f /opt/miui-dtb.dtb ]; then
    dtc -I dtb -O dts /opt/miui-dtb.dtb -o /opt/miui-dtb.dts 2>/dev/null && \
        echo "DTB decompiled: /opt/miui-dtb.dts" || \
        echo "dtc failed - might be a multi-DTB"
    ls -lh /opt/miui-dtb.dtb
fi

echo "=== DTBO partition info ==="
python3 -c "
import struct
with open('/mnt/c/Windows/Temp/miui_dtbo.img', 'rb') as f:
    hdr = f.read(32)
magic, = struct.unpack_from('>I', hdr, 0)
print(f'DTBO magic: 0x{magic:08x}')
if magic == 0xd7b7ab1e:
    total_size, hdr_size, dt_entry_size, dt_entry_count, dt_entries_offset = struct.unpack_from('>IIIII', hdr, 4)
    print(f'DTBO table: {dt_entry_count} entries')
"
