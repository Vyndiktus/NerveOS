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

# Ensure init scripts are executable
chmod +x "$TARGET_DIR/etc/init.d/S99hived" 2>/dev/null || true
chmod +x "$TARGET_DIR/etc/init.d/S80nerveos-shell" 2>/dev/null || true

# Add dbus system user if Buildroot's dbus package didn't create it
# (needed by S30dbus init script; bluetoothd requires dbus)
if ! grep -q '^dbus:' "$TARGET_DIR/etc/passwd" 2>/dev/null; then
    echo 'dbus:x:81:81:System message bus:/run/dbus:/bin/false' >> "$TARGET_DIR/etc/passwd"
fi
if ! grep -q '^dbus:' "$TARGET_DIR/etc/group" 2>/dev/null; then
    echo 'dbus:x:81:' >> "$TARGET_DIR/etc/group"
fi

# Create bluetooth config dir and minimal main.conf
mkdir -p "$TARGET_DIR/etc/bluetooth"
if [ ! -f "$TARGET_DIR/etc/bluetooth/main.conf" ]; then
    printf '[Policy]\nAutoEnable=true\n' > "$TARGET_DIR/etc/bluetooth/main.conf"
fi

# Concatenate kernel + DTB for mainline (no appended-DTB support in 6.11)
KERNEL="$BINARIES_DIR/Image"
DTB="$BINARIES_DIR/qcom/sm8150-xiaomi-cepheus.dtb"
if [ -f "$KERNEL" ] && [ -f "$DTB" ]; then
    cat "$KERNEL" "$DTB" > "$BINARIES_DIR/Image-dtb"
    echo "[NerveOS] Created Image-dtb ($(du -sh "$BINARIES_DIR/Image-dtb" | cut -f1))"
fi

echo "[NerveOS] Post-build complete."
