#!/bin/bash
set -e
K=/opt/NerveOS/build/cepheus/build/linux-cepheus-q-oss
BR_TARGET=/opt/NerveOS/build/cepheus/target

echo "=== Finding busybox and its libs ==="
BB=$(find /opt/NerveOS/build/cepheus -name "busybox" -type f 2>/dev/null | head -1)
echo "Busybox: $BB"
file "$BB"

echo "=== Building initramfs ==="
INITRD=/tmp/NerveOS-initrd
rm -rf $INITRD && mkdir -p $INITRD/{bin,sbin,proc,sys,dev,run,lib,lib64}

# Copy busybox
cp "$BB" $INITRD/bin/busybox
chmod +x $INITRD/bin/busybox

# Copy dynamic linker and essential libs from buildroot target
for lib in ld-linux-aarch64.so.1 libc.so.6 libm.so.6 libdl.so.2 libpthread.so.0 libgcc_s.so.1; do
    src=$(find $BR_TARGET/lib $BR_TARGET/lib64 -name "$lib" -type f 2>/dev/null | head -1)
    if [ -n "$src" ]; then
        cp "$src" $INITRD/lib/
        echo "  Copied: $lib"
    fi
done

# Install busybox applets
for cmd in sh mount ls echo cat sleep mkdir ln printf dmesg lsblk ip ifconfig telnetd; do
    ln -sf busybox $INITRD/bin/$cmd 2>/dev/null || true
done
ln -sf ../bin/busybox $INITRD/sbin/init 2>/dev/null || true

# Write init script
cat > $INITRD/init << 'INIT_EOF'
#!/bin/sh

# All output goes to kernel log (readable via pstore after panic)
exec > /dev/kmsg 2>&1

echo "HIVE_INIT: started"

mount -t proc none /proc
mount -t sysfs none /sys
mount -t devtmpfs devtmpfs /dev
mount -t configfs none /sys/kernel/config

echo "HIVE_INIT: mounts done"

echo "HIVE_INIT: UDC list: $(ls /sys/class/udc/ 2>/dev/null | tr '\n' ' ')"
echo "HIVE_INIT: configfs: $(ls /sys/kernel/config/ 2>/dev/null | tr '\n' ' ')"
echo "HIVE_INIT: net devs: $(ls /sys/class/net/ 2>/dev/null | tr '\n' ' ')"

# Try USB RNDIS gadget
G=/sys/kernel/config/usb_gadget/NerveOS
mkdir -p $G
echo 0x18D1 > $G/idVendor
echo 0x4EE3 > $G/idProduct
mkdir -p $G/strings/0x409
echo "NerveOS"       > $G/strings/0x409/manufacturer
echo "NerveOS Debug" > $G/strings/0x409/product
mkdir -p $G/configs/c.1
mkdir -p $G/configs/c.1/strings/0x409
echo "RNDIS" > $G/configs/c.1/strings/0x409/configuration
echo "HIVE_INIT: gadget dirs created"

if mkdir -p $G/functions/rndis.usb0 2>/dev/null; then
    echo "HIVE_INIT: rndis function OK"
    echo "12:34:56:78:9a:bc" > $G/functions/rndis.usb0/host_addr
    echo "12:34:56:78:9a:bd" > $G/functions/rndis.usb0/dev_addr
    ln -s $G/functions/rndis.usb0 $G/configs/c.1/
    UDC=$(ls /sys/class/udc/ 2>/dev/null | head -1)
    echo "HIVE_INIT: UDC=$UDC"
    echo "$UDC" > $G/UDC && echo "HIVE_INIT: UDC write OK" || echo "HIVE_INIT: UDC write FAILED"
else
    echo "HIVE_INIT: rndis function NOT available - trying serial"
    if mkdir -p $G/functions/serial.usb0 2>/dev/null; then
        echo "HIVE_INIT: serial function OK"
        ln -s $G/functions/serial.usb0 $G/configs/c.1/
        UDC=$(ls /sys/class/udc/ 2>/dev/null | head -1)
        echo "$UDC" > $G/UDC && echo "HIVE_INIT: serial UDC OK" || echo "HIVE_INIT: serial UDC FAILED"
    else
        echo "HIVE_INIT: no USB function available"
    fi
fi

echo "HIVE_INIT: net devs after gadget: $(ls /sys/class/net/ 2>/dev/null | tr '\n' ' ')"
echo "HIVE_INIT: all done - exiting to trigger pstore capture"
# Do NOT exec sh - let init exit so kernel panics and writes pstore
# Then reboot to recovery to read /sys/fs/pstore/
INIT_EOF

chmod +x $INITRD/init

# Verify busybox runs
echo "=== Verifying libs ==="
ls -la $INITRD/lib/

echo "=== Packing initramfs ==="
cd $INITRD
find . | cpio -o -H newc 2>/dev/null | gzip > /opt/NerveOS-debug-initrd.gz
ls -lh /opt/NerveOS-debug-initrd.gz

echo "=== Building debug boot image ==="
DTS=$K/arch/arm64/boot/dts/qcom

mkbootimg \
  --kernel $K/arch/arm64/boot/Image \
  --ramdisk /opt/NerveOS-debug-initrd.gz \
  --dtb $DTS/sm8150-v2.dtb \
  --cmdline "console=ttyMSM0,115200n8 console=ttyGS0,115200 earlycon=msm_geni_serial,0xa90000 androidboot.hardware=qcom androidboot.bootdevice=1d84000.ufshc loglevel=8 rdinit=/init" \
  --header_version 2 \
  --pagesize 4096 \
  --base 0x00000000 \
  --kernel_offset 0x00008000 \
  --ramdisk_offset 0x01000000 \
  --tags_offset 0x00000100 \
  --dtb_offset 0x01f00000 \
  --output /opt/boot_debug.img

echo "Done: $(ls -lh /opt/boot_debug.img)"
cp /opt/boot_debug.img "/mnt/c/Windows/Temp/NerveOS_boot_debug.img"
echo "Copied to Windows temp"
