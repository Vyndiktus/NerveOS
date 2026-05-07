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

echo "=== nerved binary ==="
file $MNT/usr/bin/nerved 2>/dev/null || file $MNT/sbin/nerved 2>/dev/null || echo "No nerved binary"

echo "=== S99nerved script ==="
cat $MNT/etc/init.d/S99nerved

echo "=== hive etc ==="
cat $MNT/etc/nerve/nerved.conf

umount $MNT
