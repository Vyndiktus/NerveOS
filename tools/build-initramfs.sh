#!/bin/bash
# Rebuild nerveos-static-initrd.gz with correct init script
set -e

SRC=/opt/initramfs-static
OUT=/opt/nerveos-static-initrd.gz

# Write a proper init script
cat > "$SRC/init" << 'INITEOF'
#!/bin/sh
mount -t proc none /proc
mount -t sysfs none /sys
mount -t devtmpfs none /dev 2>/dev/null
/bin/mdev -s 2>/dev/null
mount -t configfs none /sys/kernel/config 2>/dev/null

# UART shell - always accessible via ttyMSM0
/sbin/getty -n -l /bin/sh ttyMSM0 115200 vt100 &

echo "=== NerveOS - waiting for UDC ==="
i=0
while [ $i -lt 60 ]; do
  UDC=$(ls /sys/class/udc/ 2>/dev/null | head -1)
  if [ -n "$UDC" ]; then
    echo "UDC found after ${i}s: $UDC"
    break
  fi
  echo "Waiting... ${i}s"
  sleep 1
  i=$((i+1))
done

if [ -z "$UDC" ]; then
  echo "No UDC after 60s, dropping to shell"
  exec /bin/sh
fi

echo "=== Binding ACM gadget to $UDC ==="
G=/sys/kernel/config/usb_gadget/g0
mkdir -p "$G"
echo 0x1d6b > "$G/idVendor"
echo 0x0104 > "$G/idProduct"
mkdir -p "$G/strings/0x409"
echo NerveOS > "$G/strings/0x409/manufacturer"
echo Debug > "$G/strings/0x409/product"
echo 00000001 > "$G/strings/0x409/serialnumber"
mkdir -p "$G/functions/acm.0"
mkdir -p "$G/configs/c.1/strings/0x409"
echo 250 > "$G/configs/c.1/MaxPower"
echo "CDC ACM" > "$G/configs/c.1/strings/0x409/configuration"
ln -s "$G/functions/acm.0" "$G/configs/c.1/" 2>/dev/null
echo "$UDC" > "$G/UDC"
echo "=== ACM gadget bound ==="

# Start shell on USB ACM serial
sleep 1
/sbin/getty -n -l /bin/sh ttyGS0 115200 vt100 &

# Drop to interactive shell
exec /bin/sh
INITEOF

chmod +x "$SRC/init"

# Rebuild initramfs
cd "$SRC"
find . | cpio -o -H newc 2>/dev/null | gzip -9 > "$OUT"
echo "Built $OUT ($(stat -c%s "$OUT") bytes)"
