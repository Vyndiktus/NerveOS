#!/bin/bash
K=/opt/NerveOS/build/cepheus/build/linux-cepheus-q-oss
export ARCH=arm64
export CROSS_COMPILE=aarch64-linux-gnu-
export PATH=/opt/NerveOS/build/cepheus/host/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

echo "=== GCC version ==="
aarch64-linux-gnu-gcc --version | head -1

echo ""
echo "=== arch/arm64/Makefile march/mcpu flags ==="
grep -E "march|mcpu|mfpu|mabi|mtune|mfix|mlsx|march" $K/arch/arm64/Makefile 2>/dev/null | head -20

echo ""
echo "=== Kernel Makefile KBUILD_CFLAGS ==="
grep -E "KBUILD_CFLAGS|march|mcpu" $K/Makefile 2>/dev/null | head -20

echo ""
echo "=== What flags are actually used (from build) ==="
cd $K
# Compile a small file with verbose output to see flags
make arch/arm64/kernel/entry.o V=1 2>&1 | head -5 | grep "aarch64-linux-gnu-gcc"

echo ""
echo "=== Check for problematic instructions in kernel Image ==="
# Check for atomics/LSE instructions (ARMv8.1+)
# LDADD = 0xb8200000 family (ARMv8.1 LSE atomics)
python3 - << 'PYEOF'
data = open('/opt/NerveOS/build/cepheus/build/linux-cepheus-q-oss/arch/arm64/boot/Image', 'rb').read()

# Check for LSE atomic instructions (ARMv8.1-A)
# STADD: 0xB820001F, LDADD: various 0xB820xxxx patterns
lse_count = 0
for i in range(0, len(data)-4, 4):
    word = int.from_bytes(data[i:i+4], 'little')
    # LSE atomics: bits[31:21] = 10111000001 or similar
    if (word & 0xFF200000) == 0xB8200000 and (word & 0x0000FC00) == 0x0000FC00:
        lse_count += 1

# SWPA/LDADD etc - ARMv8.1 atomics
print(f"Potential LSE atomic instructions: {lse_count}")

# Check for PACIA/AUTIA (pointer auth, ARMv8.3)
pac_patterns = [
    b'\x1f\x20\x03\xd5',  # NOP (might be encoded PAC)
    b'\x3f\x23\x03\xd5',  # PACIASP
    b'\xbf\x23\x03\xd5',  # AUTIASP
]
for p in pac_patterns:
    count = data.count(p)
    if count > 0:
        print(f"Found {count} of {p.hex()} pattern")

print("Done checking instruction patterns")
PYEOF

echo ""
echo "=== kernel version string in Image ==="
strings /opt/NerveOS/build/cepheus/build/linux-cepheus-q-oss/arch/arm64/boot/Image | grep "Linux version" | head -3

echo ""
echo "=== MSM_RTIC / kernel protect config ==="
grep -E "^CONFIG_(MSM_RTIC|MSM_KERNEL_PROTECT|MSM_TZ_SMMU|QCOM_EAR)" \
    $K/.config 2>/dev/null
