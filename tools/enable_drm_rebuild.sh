#!/bin/bash
set -e
K=/opt/NerveOS/build/cepheus/build/linux-cepheus-q-oss
export ARCH=arm64
export CROSS_COMPILE=aarch64-linux-gnu-
export PATH=/opt/NerveOS/build/cepheus/host/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

echo "=== Enabling CONFIG_DRM=y (DRM core only, no DRM_MSM) ==="
# Remove the DRM=n line and set DRM=y
sed -i 's/# CONFIG_DRM is not set/CONFIG_DRM=y/' $K/.config

# Ensure DRM_MSM stays off
grep "CONFIG_DRM_MSM" $K/.config || echo "# CONFIG_DRM_MSM is not set" >> $K/.config

# Also ensure SDE_ROTATOR stays off (it depends on DRM_MSM which is off anyway)
echo "# CONFIG_DRM_MSM is not set" >> $K/.config
echo "# CONFIG_MSM_SDE_ROTATOR is not set" >> $K/.config

echo "Running olddefconfig..."
cd $K && make olddefconfig 2>&1 | tail -5

echo ""
echo "=== DRM config after olddefconfig ==="
grep -E "^CONFIG_(DRM|DRM_MSM|DRM_SDE|MSM_SDE)=" $K/.config

echo ""
echo "=== Building kernel (this will show any DRM compile errors) ==="
touch $K/drivers/gpu/drm/drm_sysfs.c
make -j$(nproc) Image 2>&1 | grep -E "error:|warning:|ld:|Image|undefined" | tail -30

echo ""
echo "=== Build result ==="
ls -lh $K/arch/arm64/boot/Image
