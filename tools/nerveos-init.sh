#!/bin/sh
mount -t proc none /proc
mount -t sysfs none /sys
mount -t devtmpfs none /dev 2>/dev/null
/bin/mdev -s 2>/dev/null
mount -t configfs none /sys/kernel/config 2>/dev/null

# Respawning shell on physical UART
(while true; do /sbin/getty -n -l /bin/sh ttyMSM0 115200 vt100; sleep 1; done) &

# Wait for DWC3 UDC (up to 30s)
i=0; UDC=""
while [ $i -lt 30 ]; do
  UDC=$(ls /sys/class/udc/ 2>/dev/null | head -1)
  [ -n "$UDC" ] && break
  sleep 1; i=$((i+1))
done

if [ -n "$UDC" ]; then
  sleep 2
  G=/sys/kernel/config/usb_gadget/g0
  mkdir "$G"
  mkdir "$G/strings/0x409"
  echo 0x1d6b > "$G/idVendor"
  echo 0x0104 > "$G/idProduct"
  echo "NerveOS" > "$G/strings/0x409/manufacturer"
  echo "NerveOS Serial" > "$G/strings/0x409/product"
  echo "deadbeef00000001" > "$G/strings/0x409/serialnumber"
  mkdir "$G/functions/acm.GS0"
  mkdir "$G/configs/c.1"
  mkdir "$G/configs/c.1/strings/0x409"
  echo "CDC ACM" > "$G/configs/c.1/strings/0x409/configuration"
  cd "$G" && ln -s functions/acm.GS0 configs/c.1/
  echo "$UDC" > "$G/UDC" && \
    (while true; do /sbin/getty -n -l /bin/sh ttyGS0 115200 vt100; sleep 1; done) &
fi

# Wait for UFS block device (up to 60s)
i=0
while [ $i -lt 60 ]; do
  /bin/mdev -s 2>/dev/null
  [ -b /dev/sda ] && break
  sleep 1; i=$((i+1))
done

# Dump dmesg to USB serial for diagnosis (works even if shell process dies)
{
  echo '======= NerveOS initramfs dmesg ======='
  /bin/busybox dmesg
  echo '======= /dev listing ======='
  ls -la /dev/
  echo '======= UFS sysfs ======='
  ls /sys/bus/platform/drivers/ufshcd-qcom/ 2>/dev/null || echo 'ufshcd not bound'
  ls /sys/class/scsi_host/ 2>/dev/null || echo 'no scsi_host'
  ls /sys/class/scsi_device/ 2>/dev/null || echo 'no scsi_device'
  echo '======= end ======='
} > /dev/ttyGS0 2>/dev/null

if [ -b /dev/sda ]; then
  for dev in $(ls /dev/sd* 2>/dev/null | sort); do
    [ -b "$dev" ] || continue
    mount -t ext4 -o ro "$dev" /mnt/root 2>/dev/null || continue
    if [ -x /mnt/root/sbin/init ]; then
      mount -o remount,rw /mnt/root
      mkdir -p /mnt/root/proc /mnt/root/sys /mnt/root/dev
      mount --move /proc /mnt/root/proc
      mount --move /sys /mnt/root/sys
      mount --move /dev /mnt/root/dev
      exec switch_root /mnt/root /sbin/init
    fi
    umount /mnt/root 2>/dev/null
  done
fi

echo '[NerveOS] No rootfs. Emergency shell on ttyGS0 and ttyMSM0.' > /dev/ttyGS0 2>/dev/null
while true; do sleep 60; done
