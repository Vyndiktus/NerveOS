#!/bin/bash
# Rebuild kernel with CONFIG_RELOCATABLE=y.
# Clears kconfig stamps to force olddefconfig re-run, keeps compiled objects
# so only changed/dependent files recompile.
set -e

BR=/opt/NerveOS/build/cepheus
K=$BR/build/linux-cepheus-q-oss
STAMP_DIR=$BR/build/linux-cepheus-q-oss

export ARCH=arm64
export CROSS_COMPILE=aarch64-linux-gnu-
export PATH=$BR/host/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

echo "=== Clearing kconfig stamps (keep .stamp_patched, keep .stamp_extracted) ==="
for stamp in .stamp_kconfig_fixup_done .stamp_dotconfig .stamp_configured .stamp_built; do
    if [ -f "$STAMP_DIR/$stamp" ]; then
        rm "$STAMP_DIR/$stamp"
        echo "  Removed: $stamp"
    fi
done

echo ""
echo "=== Merging config fragment into kernel .config ==="
cd $K

# Apply the NerveOS config fragment on top of the existing .config
# Using merge_config.sh if available, otherwise manual approach
FRAGMENT=$'/mnt/c/Users/Forbidden User/NerveOS/br2-external/board/cepheus/kernel-NerveOS.config'

# Append fragment entries then run olddefconfig (avoids merge_config.sh space issues)
cat "$FRAGMENT" >> .config
make olddefconfig

echo ""
echo "=== Verifying RELOCATABLE in .config ==="
grep "CONFIG_RELOCATABLE\|CONFIG_RANDOMIZE_BASE\|CONFIG_KALLSYMS_BASE_RELATIVE" .config

echo ""
echo "=== Rebuilding kernel (only changed objects will recompile) ==="
make -j$(nproc) Image 2>&1 | grep -E "error:|Error|ld:.*undefined|Image built|Kernel:|arch/arm64/boot/Image" | tail -30

echo ""
echo "=== Build result ==="
ls -lh $K/arch/arm64/boot/Image

echo ""
echo "=== Building boot image ==="
bash $'/mnt/c/Users/Forbidden User/NerveOS/tools/build_v1_boot.sh'
