#!/bin/bash
# Post-build script for cepheus — runs inside Buildroot after rootfs is assembled
set -e

BOARD_DIR="$(dirname "$0")"
TARGET_DIR="$1"
BINARIES_DIR="$(dirname "$TARGET_DIR")/images"

echo "[NerveOS] Post-build: cepheus"

# Install default hive config if not present
if [ ! -f "$TARGET_DIR/etc/hive/hived.conf" ]; then
    mkdir -p "$TARGET_DIR/etc/hive"
    cp "$BOARD_DIR/hived.conf.default" "$TARGET_DIR/etc/hive/hived.conf"
fi

# Ensure init script is executable
chmod +x "$TARGET_DIR/etc/init.d/S99hived" 2>/dev/null || true

# Concatenate kernel + DTB for mainline (no appended-DTB support in 6.11)
KERNEL="$BINARIES_DIR/Image"
DTB="$BINARIES_DIR/qcom/sm8150-xiaomi-cepheus.dtb"
if [ -f "$KERNEL" ] && [ -f "$DTB" ]; then
    cat "$KERNEL" "$DTB" > "$BINARIES_DIR/Image-dtb"
    echo "[NerveOS] Created Image-dtb ($(du -sh "$BINARIES_DIR/Image-dtb" | cut -f1))"
fi

echo "[NerveOS] Post-build complete."
