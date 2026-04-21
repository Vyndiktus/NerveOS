#!/bin/bash
echo "=== Buildroot images ==="
ls -lh /opt/NerveOS/build/cepheus/images/ 2>/dev/null

echo "=== rootfs.ext4 details ==="
file /opt/NerveOS/build/cepheus/images/rootfs.ext4 2>/dev/null

echo "=== Check ext4 superblock ==="
dumpe2fs /opt/NerveOS/build/cepheus/images/rootfs.ext4 2>/dev/null | head -20

echo "=== What was flashed to system partition? ==="
ls -lh /opt/NerveOS/build/cepheus/images/rootfs.ext4.sparse 2>/dev/null || echo "No sparse file"
ls -lh /tmp/rootfs*.sparse 2>/dev/null || echo "No sparse in /tmp"

echo "=== Check if we have a valid rootfs ==="
mkdir -p /tmp/rootfs_check
mount -o loop,ro /opt/NerveOS/build/cepheus/images/rootfs.ext4 /tmp/rootfs_check 2>/dev/null && {
    echo "Mounted OK. Contents:"
    ls /tmp/rootfs_check/
    echo "--- /sbin ---"
    ls /tmp/rootfs_check/sbin/ 2>/dev/null | head -10
    umount /tmp/rootfs_check
} || echo "Mount FAILED"
