#!/usr/bin/env python3
"""
hive-flash — NerveOS image flasher

Flashes a pre-built NerveOS image onto a connected device via fastboot.

Usage:
    python hive-flash.py --device cepheus [--serial SERIAL] [--images-dir PATH]

Prerequisites:
    - Device must be in fastboot mode (Vol- + Power on Mi 9)
    - Bootloader must be unlocked
    - Images built via: make DEVICE=cepheus
"""

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

import yaml

DEVICES_DIR  = Path(__file__).parent.parent / "devices"
IMAGES_DIR   = Path(__file__).parent.parent / "build" / "images"


def run(cmd: list[str], timeout: int = 300) -> tuple[int, str, str]:
    print(f"  $ {' '.join(cmd)}")
    r = subprocess.run(cmd, capture_output=False, timeout=timeout)
    return r.returncode, "", ""


def run_capture(cmd: list[str], timeout: int = 10) -> tuple[int, str, str]:
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return r.returncode, r.stdout.strip(), r.stderr.strip()


def load_profile(device_id: str) -> dict:
    path = DEVICES_DIR / f"{device_id}.yaml"
    if not path.exists():
        sys.exit(f"[ERROR] No device profile found: {path}")
    with open(path) as f:
        return yaml.safe_load(f)


def find_serial(device_id: str, preferred: str | None) -> str:
    code, out, _ = run_capture(["fastboot", "devices"])
    devices = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "fastboot":
            devices.append(parts[0])

    if not devices:
        sys.exit("[ERROR] No devices found in fastboot mode.\n"
                 "  Hold Vol- + Power to enter fastboot, then retry.")

    if preferred:
        if preferred in devices:
            return preferred
        sys.exit(f"[ERROR] Serial {preferred} not found. Connected: {devices}")

    if len(devices) > 1:
        print(f"[!] Multiple devices detected: {devices}")
        print(f"    Specify one with --serial SERIAL")
        sys.exit(1)

    return devices[0]


def check_unlocked(serial: str) -> bool:
    code, out, err = run_capture(["fastboot", "-s", serial, "getvar", "unlocked"])
    combined = out + err
    for line in combined.splitlines():
        if "unlocked:" in line:
            return "yes" in line
    return False


def verify_images(profile: dict, images_dir: Path) -> dict[str, Path]:
    found = {}
    missing = []
    for step in profile.get("flash_sequence", []):
        img_name = step["image"]
        img_path = images_dir / img_name
        if img_path.exists():
            found[step["partition"]] = img_path
        else:
            missing.append(str(img_path))

    if missing:
        print("[ERROR] Missing image files:")
        for m in missing:
            print(f"  - {m}")
        print(f"\nBuild images first: make DEVICE={profile['id']}")
        sys.exit(1)

    return found


def flash_device(serial: str, profile: dict, images_dir: Path, dry_run: bool):
    print(f"\n[NerveOS] Flashing {profile['name']} ({serial})")
    print(f"         Images: {images_dir}\n")

    image_map = verify_images(profile, images_dir)

    for step in profile.get("flash_sequence", []):
        partition = step["partition"]
        flags = step.get("flags", [])
        img_path = image_map[partition]

        cmd = ["fastboot", "-s", serial] + flags + ["flash", partition, str(img_path)]

        print(f"\n  Flashing partition: {partition}")
        print(f"  Image:  {img_path.name} ({img_path.stat().st_size // 1024 // 1024} MB)")

        if dry_run:
            print(f"  [DRY RUN] Would run: {' '.join(cmd)}")
        else:
            code, _, _ = run(cmd, timeout=120)
            if code != 0:
                sys.exit(f"[ERROR] Flash failed on partition: {partition}")

    if not dry_run:
        print("\n  Rebooting device...")
        run(["fastboot", "-s", serial, "reboot"], timeout=30)
        print("\n[NerveOS] Flash complete! Device is booting NerveOS.")
        print("         hived will start automatically and attempt to join the hive.")
    else:
        print("\n[DRY RUN] Flash sequence complete (no changes made).")


def main():
    parser = argparse.ArgumentParser(description="NerveOS image flasher")
    parser.add_argument("--device", required=True,
                        help="Device ID (e.g. cepheus)")
    parser.add_argument("--serial",
                        help="Fastboot serial number (auto-detected if only one device)")
    parser.add_argument("--images-dir", type=Path,
                        help="Directory containing built images (default: build/images/DEVICE)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be flashed without writing anything")
    args = parser.parse_args()

    profile = load_profile(args.device)
    serial  = find_serial(args.device, args.serial)

    images_dir = args.images_dir or (IMAGES_DIR / args.device)

    print(f"[NerveOS] Device profile : {profile['name']}")
    print(f"[NerveOS] Target serial  : {serial}")
    print(f"[NerveOS] Images dir     : {images_dir}")

    # Safety check: bootloader unlocked?
    if not args.dry_run:
        if not check_unlocked(serial):
            print("\n[ERROR] Bootloader is LOCKED.")
            if profile.get("bootloader", {}).get("unlock_notes"):
                print("\nUnlock instructions:")
                print(profile["bootloader"]["unlock_notes"])
            sys.exit(1)

        confirm = input(f"\n[!] About to flash NerveOS onto {profile['name']} ({serial}).\n"
                        f"    This will ERASE all data. Type 'yes' to continue: ")
        if confirm.strip().lower() != "yes":
            print("Aborted.")
            sys.exit(0)

    flash_device(serial, profile, images_dir, args.dry_run)


if __name__ == "__main__":
    main()
