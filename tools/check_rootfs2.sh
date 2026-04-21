#!/bin/bash
IMG=/opt/NerveOS/build/cepheus/images/rootfs.ext4
MNT=/tmp/rootfs_check
mkdir -p $MNT
mount -o loop,ro $IMG $MNT 2>/dev/null || { echo "Mount failed"; exit 1; }

echo "=== S10udev script ==="
cat $MNT/etc/init.d/S10udev

echo "=== udevd/udevadm binary? ==="
ls $MNT/sbin/udev* $MNT/bin/udev* 2>/dev/null || echo "No udev binary"
ls $MNT/lib/udev/ 2>/dev/null | head -5 || echo "No udev lib"

echo "=== hived binary ==="
file $MNT/usr/bin/hived 2>/dev/null || file $MNT/sbin/hived 2>/dev/null || echo "No hived binary"

echo "=== S99hived script ==="
cat $MNT/etc/init.d/S99hived

echo "=== hive etc ==="
cat $MNT/etc/hive/hived.conf

umount $MNT
