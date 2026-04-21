#!/bin/bash
set -e
K=/opt/NerveOS/build/cepheus/build/linux-cepheus-q-oss
SYSFS=$K/drivers/gpu/drm/drm_sysfs.c

echo "=== Patching drm_sysfs.c to guard mipi_reg calls with CONFIG_DRM_MSM ==="

# Guard the mipi_reg extern declarations and implementations
python3 << 'PYEOF'
with open('/opt/NerveOS/build/cepheus/build/linux-cepheus-q-oss/drivers/gpu/drm/drm_sysfs.c', 'r') as f:
    content = f.read()

old = '''extern ssize_t mipi_reg_write(char *buf, size_t count);
extern ssize_t mipi_reg_read(char *buf);

static ssize_t mipi_reg_show(struct device *device,
\t\t\t    struct device_attribute *attr,
\t\t\t   char *buf)
{
\treturn mipi_reg_read(buf);
}

static ssize_t mipi_reg_store(struct device *device,
\t\t\t   struct device_attribute *attr,
\t\t\t   const char *buf, size_t count)
{
\tint rc = 0;

\trc = mipi_reg_write((char *)buf, count);
\treturn rc;
}'''

new = '''#ifdef CONFIG_DRM_MSM
extern ssize_t mipi_reg_write(char *buf, size_t count);
extern ssize_t mipi_reg_read(char *buf);

static ssize_t mipi_reg_show(struct device *device,
\t\t\t    struct device_attribute *attr,
\t\t\t   char *buf)
{
\treturn mipi_reg_read(buf);
}

static ssize_t mipi_reg_store(struct device *device,
\t\t\t   struct device_attribute *attr,
\t\t\t   const char *buf, size_t count)
{
\tint rc = 0;

\trc = mipi_reg_write((char *)buf, count);
\treturn rc;
}
#else
static ssize_t mipi_reg_show(struct device *device,
\t\t\t    struct device_attribute *attr,
\t\t\t   char *buf) { return -ENODEV; }
static ssize_t mipi_reg_store(struct device *device,
\t\t\t   struct device_attribute *attr,
\t\t\t   const char *buf, size_t count) { return -ENODEV; }
#endif'''

if old in content:
    content = content.replace(old, new)
    with open('/opt/NerveOS/build/cepheus/build/linux-cepheus-q-oss/drivers/gpu/drm/drm_sysfs.c', 'w') as f:
        f.write(content)
    print('Patched drm_sysfs.c successfully')
else:
    print('ERROR: Pattern not found - check drm_sysfs.c manually')
    import sys; sys.exit(1)
PYEOF

echo ""
echo "=== Rebuilding kernel ==="
export ARCH=arm64
export CROSS_COMPILE=aarch64-linux-gnu-
export PATH=/opt/NerveOS/build/cepheus/host/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

cd $K
touch drivers/gpu/drm/drm_sysfs.c
make -j$(nproc) Image 2>&1 | grep -E "error:|Error|ld:.*undefined|Image built|Kernel:" | tail -20

echo ""
echo "=== Build result ==="
ls -lh $K/arch/arm64/boot/Image
