#!/bin/bash
# WSL2 build script for NerveOS — run as root inside Debian WSL2
# Launch from Windows PowerShell:
#   Start-Process wsl.exe -ArgumentList '-d','Debian','-u','root','/opt/NerveOS-project/nerveos-build.sh' -WindowStyle Hidden
#
# First-time setup (once per WSL2 session — mount is lost on restart):
#   wsl -d Debian -u root -e bash -c "mkdir -p /opt/NerveOS-project && mount --bind '/mnt/c/Users/Forbidden User/HiveOS' /opt/NerveOS-project"
#
# Buildroot cannot handle spaces in paths; the bind mount provides a space-free alias.
set -e
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export HOME=/root
export FORCE_UNSAFE_CONFIGURE=1
export TERM=linux

SRC=/opt/NerveOS-project
BUILD=/opt/NerveOS/build/cepheus
LOG=$BUILD/build.log

# Re-create bind mount if it was lost (WSL2 restart)
if [ ! -f $SRC/Makefile ]; then
    mkdir -p $SRC
    mount --bind '/mnt/c/Users/Forbidden User/HiveOS' $SRC
fi

mkdir -p $BUILD
echo "[NerveOS] Build started: $(date)" > $LOG
echo "[NerveOS] Reloading defconfig..." >> $LOG
make -C $SRC/buildroot BR2_EXTERNAL=$SRC/br2-external O=$BUILD NerveOS_cepheus_defconfig >> $LOG 2>&1
echo "[NerveOS] Starting full build..." >> $LOG
make -C $SRC/buildroot BR2_EXTERNAL=$SRC/br2-external O=$BUILD -j$(nproc) >> $LOG 2>&1
echo "EXIT:$?" >> $LOG
echo "[NerveOS] Build complete: $(date)" >> $LOG
