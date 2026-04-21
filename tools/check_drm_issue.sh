#!/bin/bash
K=/opt/NerveOS/build/cepheus/build/linux-cepheus-q-oss

echo "=== drm_sysfs.c MSM-specific calls ==="
grep -n "msm_\|sde_\|QCOM\|qcom" $K/drivers/gpu/drm/drm_sysfs.c 2>/dev/null | head -30

echo ""
echo "=== What does drm core depend on from MSM? ==="
grep -rn "msm_get_connector\|sde_get\|drm_msm" $K/drivers/gpu/drm/drm_*.c 2>/dev/null | head -20

echo ""
echo "=== Check if enabling DRM=y without DRM_MSM would cause undefined symbols ==="
# Look at what MSM symbols drm_sysfs.c uses that would be undefined
grep -n "msm_\|sde_" $K/drivers/gpu/drm/drm_sysfs.c 2>/dev/null

echo ""
echo "=== Alternative: what symbol errors happened when DRM was enabled? ==="
# Check drm_sysfs for CONFIG guards
grep -n "ifdef\|CONFIG" $K/drivers/gpu/drm/drm_sysfs.c 2>/dev/null | head -30

echo ""
echo "=== Check if DRM_MSM can be enabled now (do errors remain?) ==="
# Key: with our patches 0004 and 0005, can DRM_MSM=y compile?
# Check if the original problem files still exist
echo "Checking sde_hw_rot.o entry in Makefile:"
grep "sde_hw_rot" $K/drivers/gpu/drm/msm/Makefile 2>/dev/null || echo "sde_hw_rot NOT in Makefile (patch 0004 applied)"

echo ""
echo "thermal_core.c DRM guard:"
grep -n "CONFIG_DRM" $K/drivers/thermal/thermal_core.c 2>/dev/null | head -5
