#!/bin/bash
OUR=/opt/NerveOS/build/cepheus/build/linux-cepheus-q-oss/.config
REC=/mnt/c/Windows/Temp/recovery_config.txt

echo "=== ARMv8.3+ features (SM8150 is ARMv8.2, these would CRASH) ==="
echo "Ours:"
grep -E "^CONFIG_(ARM64_PTR_AUTH|ARM64_BTI|ARM64_MTE|ARM64_E0PD|ARM64_AMU_EXTN|CC_HAS_BRANCH_PROT|ARM64_PAN|ARM64_VHE)" $OUR 2>/dev/null
echo "Recovery:"
grep -E "^CONFIG_(ARM64_PTR_AUTH|ARM64_BTI|ARM64_MTE|ARM64_E0PD|ARM64_AMU_EXTN|CC_HAS_BRANCH_PROT|ARM64_PAN|ARM64_VHE)" $REC 2>/dev/null

echo ""
echo "=== Shadow call stack (needs hardware/compiler support) ==="
echo "Ours:"
grep -E "^CONFIG_(SHADOW_CALL_STACK|CC_HAS_SHADOW_CALL)" $OUR 2>/dev/null
echo "Recovery:"
grep -E "^CONFIG_(SHADOW_CALL_STACK|CC_HAS_SHADOW_CALL)" $REC 2>/dev/null

echo ""
echo "=== Stack protection ==="
echo "Ours:"
grep -E "^CONFIG_(STACKPROTECTOR|CC_STACKPROTECTOR|SCHED_STACK)" $OUR 2>/dev/null
echo "Recovery:"
grep -E "^CONFIG_(STACKPROTECTOR|CC_STACKPROTECTOR|SCHED_STACK)" $REC 2>/dev/null

echo ""
echo "=== LTO / CFI (Clang-only features) ==="
echo "Ours:"
grep -E "^CONFIG_(LTO|CFI|THINLTO|CLANG)" $OUR 2>/dev/null
echo "Recovery:"
grep -E "^CONFIG_(LTO|CFI|THINLTO|CLANG)" $REC 2>/dev/null

echo ""
echo "=== Check actual compiler flags used for kernel ==="
grep "CONFIG_CC_VERSION_TEXT\|CONFIG_CLANG_VERSION\|GCC_VERSION" $OUR 2>/dev/null | head -5

echo ""
echo "=== Check if Image has pointer auth instructions ==="
# Look for PAC instruction bytes in the kernel image
# PAC instructions have specific encodings
K=/opt/NerveOS/build/cepheus/build/linux-cepheus-q-oss
if [ -f $K/arch/arm64/boot/Image ]; then
    echo "Checking for PACIASP pattern (0xd503233f) in Image..."
    python3 -c "
data = open('$K/arch/arm64/boot/Image','rb').read()
pac = b'\x3f\x23\x03\xd5'  # paciasp instruction (little endian)
count = data.count(pac)
print(f'Found {count} PACIASP instructions in kernel Image')
if count > 0:
    print('WARNING: Kernel has pointer auth instructions - SM8150 does NOT support ARMv8.3-A PA!')
else:
    print('OK: No pointer auth instructions found')
"
fi
