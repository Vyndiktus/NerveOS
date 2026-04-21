#!/bin/bash
# WSL2 build script for NerveOS — run as root inside Debian WSL2
# Launch from Windows: wsl -d Debian -u root bash /mnt/c/Users/Forbidden\ User/HiveOS/nerveos-build.sh
set -e
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export HOME=/root
export FORCE_UNSAFE_CONFIGURE=1
export TERM=linux

SRC="/mnt/c/Users/Forbidden User/HiveOS"
BUILD=/opt/NerveOS/build/cepheus
LOG=$BUILD/build.log

mkdir -p $BUILD
echo "[NerveOS] Build started: $(date)" >> $LOG 2>&1
echo "[NerveOS] Reloading defconfig..." >> $LOG 2>&1
make -C "$SRC/buildroot" BR2_EXTERNAL="$SRC/br2-external" O=$BUILD NerveOS_cepheus_defconfig >> $LOG 2>&1
echo "[NerveOS] Starting full build..." >> $LOG 2>&1
make -C "$SRC/buildroot" BR2_EXTERNAL="$SRC/br2-external" O=$BUILD -j$(nproc) >> $LOG 2>&1
echo "EXIT:$?" >> $LOG
echo "[NerveOS] Build complete: $(date)" >> $LOG 2>&1
