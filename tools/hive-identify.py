#!/usr/bin/env python3
"""
hive-identify — NerveOS USB device identifier

Detects connected Android devices via fastboot or ADB,
matches them against the NerveOS device registry, and
reports their NerveOS build status.

Usage:
    python hive-identify.py [--watch] [--devices-dir PATH]
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import yaml  # pip install pyyaml

DEVICES_DIR = Path(__file__).parent.parent / "devices"
POLL_INTERVAL = 2  # seconds


def run(cmd: list[str], timeout: int = 5) -> tuple[int, str, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except FileNotFoundError:
        return -1, "", f"command not found: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return -1, "", "timeout"


def load_device_profiles(devices_dir: Path) -> dict:
    profiles = {}
    for f in devices_dir.glob("*.yaml"):
        with open(f) as fh:
            p = yaml.safe_load(fh)
            profiles[p["id"]] = p
    return profiles


def get_fastboot_devices() -> list[dict]:
    code, out, _ = run(["fastboot", "devices"])
    devices = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "fastboot":
            devices.append({"serial": parts[0], "mode": "fastboot"})
    return devices


def get_adb_devices() -> list[dict]:
    code, out, _ = run(["adb", "devices"])
    devices = []
    for line in out.splitlines()[1:]:  # skip header
        parts = line.split()
        if len(parts) == 2 and parts[1] in ("device", "recovery"):
            devices.append({"serial": parts[0], "mode": "adb"})
    return devices


def identify_fastboot(serial: str) -> dict:
    info = {}
    vars_to_query = ["product", "variant", "version-bootloader", "serialno", "unlocked"]
    for var in vars_to_query:
        code, out, err = run(["fastboot", "-s", serial, "getvar", var])
        # fastboot prints to stderr
        for line in (out + "\n" + err).splitlines():
            if line.startswith(f"{var}:"):
                info[var] = line.split(":", 1)[1].strip()
    return info


def identify_adb(serial: str) -> dict:
    props = ["ro.product.device", "ro.product.model", "ro.product.brand",
             "ro.build.version.release", "ro.serialno"]
    info = {}
    for prop in props:
        code, out, _ = run(["adb", "-s", serial, "shell", f"getprop {prop}"])
        if code == 0 and out:
            key = prop.replace("ro.", "").replace(".", "_")
            info[key] = out
    return info


def match_profile(device_info: dict, profiles: dict) -> dict | None:
    # Try to match by codename/product
    codename = (
        device_info.get("product") or
        device_info.get("product_device") or
        ""
    ).lower()

    if codename in profiles:
        return profiles[codename]

    # Fuzzy match: check if codename appears in any profile id
    for pid, profile in profiles.items():
        if pid in codename or codename in pid:
            return profile

    return None


def print_device_report(serial: str, mode: str, device_info: dict, profile: dict | None):
    print(f"\n{'='*60}")
    print(f"  Device detected via {mode.upper()}")
    print(f"  Serial : {serial}")

    if mode == "fastboot":
        print(f"  Product: {device_info.get('product', 'unknown')}")
        print(f"  BL ver : {device_info.get('version-bootloader', 'unknown')}")
        unlocked = device_info.get("unlocked", "unknown")
        print(f"  Unlocked: {unlocked}")
        if unlocked != "yes":
            print("  [!] Bootloader is LOCKED — unlock required before flashing NerveOS")
    else:
        print(f"  Device : {device_info.get('product_device', 'unknown')}")
        print(f"  Model  : {device_info.get('product_model', 'unknown')}")
        print(f"  Android: {device_info.get('build_version_release', 'unknown')}")

    if profile:
        print(f"\n  [✓] Matched NerveOS profile: {profile['name']} ({profile['id']})")
        print(f"      Arch  : {profile['arch']}")
        print(f"      SoC   : {profile['soc']}")
        print(f"      Flash : hive-flash.py --device {profile['id']} --serial {serial}")
        if profile.get("bootloader", {}).get("unlock_required"):
            print(f"      Unlock: see docs/unlock-{profile['id']}.md")
    else:
        codename = device_info.get("product") or device_info.get("product_device", "unknown")
        print(f"\n  [!] No NerveOS profile found for: {codename}")
        print(f"      To add support: create devices/{codename}.yaml")

    print(f"{'='*60}")


def scan_once(profiles: dict, seen: set) -> set:
    current = set()
    all_devices = []

    fb = get_fastboot_devices()
    for d in fb:
        d["info"] = identify_fastboot(d["serial"])
        all_devices.append(d)
        current.add(d["serial"])

    adb = get_adb_devices()
    for d in adb:
        d["info"] = identify_adb(d["serial"])
        all_devices.append(d)
        current.add(d["serial"])

    # Report newly connected devices
    for d in all_devices:
        if d["serial"] not in seen:
            profile = match_profile(d["info"], profiles)
            print_device_report(d["serial"], d["mode"], d["info"], profile)

    # Report disconnected devices
    for s in seen - current:
        print(f"\n  [~] Device disconnected: {s}")

    return current


def main():
    parser = argparse.ArgumentParser(description="NerveOS USB device identifier")
    parser.add_argument("--watch", action="store_true",
                        help="Continuously watch for device connections/disconnections")
    parser.add_argument("--devices-dir", type=Path, default=DEVICES_DIR,
                        help="Path to device profiles directory")
    parser.add_argument("--json", action="store_true",
                        help="Output JSON (single scan only)")
    args = parser.parse_args()

    profiles = load_device_profiles(args.devices_dir)
    print(f"[NerveOS] Loaded {len(profiles)} device profile(s): {', '.join(profiles.keys())}")

    if args.watch:
        print(f"[NerveOS] Watching for USB devices (poll every {POLL_INTERVAL}s)... Ctrl+C to stop\n")
        seen = set()
        try:
            while True:
                seen = scan_once(profiles, seen)
                time.sleep(POLL_INTERVAL)
        except KeyboardInterrupt:
            print("\n[NerveOS] Stopped.")
    else:
        scan_once(profiles, set())


if __name__ == "__main__":
    main()
