#!/usr/bin/env python3
"""Build boot_bt_fix.img: EFI=n kernel + BT pinctrl DTB + v37 ramdisk."""
import struct, subprocess, sys

V37_IMG = "/opt/boot_nerveos_v37.img"
DTB = "/opt/NerveOS/build/cepheus/build/linux-4a8d88483/arch/arm64/boot/dts/qcom/sm8150-xiaomi-cepheus.dtb"
OUT = "/opt/boot_bt_fix.img"

CMDLINE = ("nomodeset clk_ignore_unused pd_ignore_unused "
           "console=tty0 console=ttyMSM0,115200n8 "
           "earlycon=qcom_geni,0xa90000 loglevel=8 rdinit=/init")

# Parse Android boot image v1 header (mkbootimg v0 layout)
# Magic: 8 bytes, then 10 uint32 fields
with open(V37_IMG, "rb") as f:
    data = f.read()

magic = data[:8]
assert magic == b"ANDROID!", f"Bad magic: {magic}"

(k_sz, k_addr, r_sz, r_addr, second_sz, second_addr,
 tags_addr, page_sz, header_version, os_version) = struct.unpack_from("<10I", data, 8)

print(f"Page size: {page_sz}")
print(f"Kernel size: {k_sz}")
print(f"Ramdisk size: {r_sz}")
print(f"Header version: {header_version}")

def page_align(n, page=page_sz):
    return ((n + page - 1) // page) * page

# Header is 1 page
header_pages = 1
kernel_pages = page_align(k_sz) // page_sz
ramdisk_offset = (header_pages + kernel_pages) * page_sz

kernel_blob = data[page_sz : page_sz + k_sz]
ramdisk_blob = data[ramdisk_offset : ramdisk_offset + r_sz]

print(f"Kernel blob: {len(kernel_blob)} bytes (offset 0x{page_sz:x})")
print(f"Ramdisk blob: {len(ramdisk_blob)} bytes (offset 0x{ramdisk_offset:x})")

# Load new DTB
with open(DTB, "rb") as f:
    dtb_data = f.read()
print(f"DTB: {len(dtb_data)} bytes")

# Kernel for Mi 9 v1 format = Image.gz + DTB concatenated
# Extract Image.gz part (strip old DTB if present)
# The Image.gz magic is 0x1f8b (gzip). Find the end of actual gzip stream.
# Simpler: v37 kernel was built as Image.gz + old DTB. We strip the old DTB.
# Find gzip end: scan from end for last 0x1f8b, or just use the DTB magic to split.
# DTB magic: 0xd00dfeed (big-endian)
dtb_magic = b'\xd0\x0d\xfe\xed'
# Find last occurrence of DTB magic in kernel blob
last_dtb = kernel_blob.rfind(dtb_magic)
if last_dtb > 0:
    print(f"Found embedded DTB at offset {last_dtb} in kernel blob — stripping")
    kernel_gz = kernel_blob[:last_dtb]
else:
    # No embedded DTB — kernel blob is just Image.gz
    kernel_gz = kernel_blob
    print("No embedded DTB found — kernel blob is Image.gz only")

print(f"Image.gz: {len(kernel_gz)} bytes")

# Concatenate new DTB
new_kernel_blob = kernel_gz + dtb_data
print(f"New kernel blob (Image.gz + new DTB): {len(new_kernel_blob)} bytes")

# Write tmp files and call mkbootimg
with open("/tmp/kernel_bt.gz", "wb") as f:
    f.write(new_kernel_blob)
with open("/tmp/ramdisk_bt.gz", "wb") as f:
    f.write(ramdisk_blob)

# Read cmdline from existing image
cmdline_offset = 8 + 10*4  # after magic + 10 uint32
cmdline_raw = data[cmdline_offset : cmdline_offset + 512]
old_cmdline = cmdline_raw.split(b'\x00')[0].decode()
print(f"Old cmdline: {old_cmdline}")

result = subprocess.run([
    "mkbootimg",
    "--kernel", "/tmp/kernel_bt.gz",
    "--ramdisk", "/tmp/ramdisk_bt.gz",
    "--cmdline", CMDLINE,
    "--base", "0x00000000",
    "--kernel_offset", f"0x{k_addr:08x}",
    "--ramdisk_offset", f"0x{r_addr:08x}",
    "--tags_offset", f"0x{tags_addr:08x}",
    "--pagesize", str(page_sz),
    "--header_version", "0",
    "--output", OUT,
], capture_output=True, text=True)

if result.returncode != 0:
    print(f"mkbootimg failed: {result.stderr}")
    sys.exit(1)

print(f"Boot image written: {OUT}")
import os
print(f"Size: {os.path.getsize(OUT)} bytes")
