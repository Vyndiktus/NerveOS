# SM8150: EFI stub silently overrides appended DTB — use CONFIG_EFI=n

**Hardware:** Qualcomm SM8150 (Snapdragon 855), ABL (Android Bootloader / UEFI)  
**Kernel:** mainline 6.11  
**Symptom:** Kernel boots but ignores your DTS changes (UFS disabled, wrong clocks,
wrong regulators) even though the DTB is correctly appended to the kernel image

---

## The problem

SM8150 uses Qualcomm's ABL, which is a UEFI-based bootloader. When the kernel is
built with `CONFIG_EFI=y` and `CONFIG_EFI_STUB=y`, it boots via the EFI stub.

The EFI stub receives the device tree via the EFI system table — a DTB that ABL
provides from its own internal table. This DTB is typically a minimal or outdated
version that matches the stock firmware (Android) configuration. UFS, display, and
power management nodes may be disabled or misconfigured relative to your mainline
DTS.

**The critical behaviour:** the EFI stub uses the EFI-provided DTB and
**ignores the DTB appended to the kernel image** (the one you compiled from your
modified `.dts` file). Your DTS changes have no effect. The kernel sees ABL's DTB
instead.

This is silent — there are no warnings, no "ignoring appended DTB" messages.

---

## The diagnostic

If your DTS changes (added nodes, changed voltages, enabled peripherals) have no
effect at runtime, check whether `CONFIG_EFI=y` is set:

```bash
zcat /proc/config.gz | grep CONFIG_EFI
# CONFIG_EFI=y          ← problem
# CONFIG_EFI_STUB=y     ← problem
```

Or check the boot log:
```
[    0.000000] UEFI: mem00: ...
[    0.000000] EFI stub: ...
```
If you see EFI stub output, the EFI path is active.

---

## The fix

Add to your kernel config fragment:

```
CONFIG_EFI=n
CONFIG_EFI_STUB=n
```

With EFI disabled, the kernel uses the native ARM64 boot protocol. ABL passes
the DTB via register `x3` (the standard ARM64 boot convention). For `fastboot boot`
or `fastboot flash boot`, the DTB you appended to the kernel image is used:

```bash
cat Image.gz sm8150-xiaomi-cepheus.dtb > kernel_with_dtb.gz
mkbootimg --kernel kernel_with_dtb.gz --ramdisk ramdisk.img \
          --cmdline "..." --base 0x0 --pagesize 4096 -o boot.img
```

After this change, all DTS modifications take effect correctly.

---

## Why this matters more than it seems

The ABL's internal DTB typically has:
- UFS (`ufshc`, `ufs_mem_phy`) **disabled** or with wrong power supplies
- PMIC regulators at stock Android voltages
- Display/DSI configured for Android's display stack

If you are running mainline Linux and made careful DTS changes to enable hardware,
`CONFIG_EFI=y` silently defeats all of them. This is the first thing to check when
hardware that should be enabled based on your DTS isn't working.

---

## Affected platforms

Any Qualcomm platform using ABL (UEFI) with mainline Linux:
- SM8150 (Snapdragon 855) — confirmed
- SDM845 (Snapdragon 845) — same ABL design, same behaviour expected
- Other Snapdragon ABL platforms (SM8250, SM8350, etc.) — likely affected

---

## Note on `fastboot boot` vs flashed images

Both `fastboot boot <image>` (RAM boot) and `fastboot flash boot <image>` (flashed)
behave the same way with respect to this issue — if `CONFIG_EFI=y`, ABL's DTB
wins in both cases.
