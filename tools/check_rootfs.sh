#!/bin/bash
IMG=/opt/NerveOS/build/cepheus/images/rootfs.ext4
MNT=/tmp/rootfs_check
mkdir -p $MNT
mount -o loop,ro $IMG $MNT 2>/dev/null || { echo "Mount failed"; exit 1; }

echo "=== /sbin/init ==="
ls -la $MNT/sbin/init 2>/dev/null || echo "NO /sbin/init!"
file $MNT/sbin/init 2>/dev/null

echo "=== /etc/inittab ==="
cat $MNT/etc/inittab 2>/dev/null || echo "No inittab"

echo "=== /etc/fstab ==="
cat $MNT/etc/fstab 2>/dev/null || echo "No fstab"

echo "=== /etc/init.d ==="
ls $MNT/etc/init.d/ 2>/dev/null

echo "=== /usr/bin/nerve CLI ==="
file $MNT/usr/bin/nerve 2>/dev/null || echo "No hive CLI"

echo "=== /etc/nerve ==="
ls $MNT/etc/nerve/ 2>/dev/null || echo "No /etc/nerve"

echo "=== /sbin/mdev or udev ==="
ls -la $MNT/sbin/mdev 2>/dev/null || echo "No mdev"

echo "=== Key libs ==="
ls $MNT/lib/ 2>/dev/null | head -10

umount $MNT
