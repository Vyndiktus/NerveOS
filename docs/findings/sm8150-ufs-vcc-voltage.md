# SM8150 UFS fails to enumerate: VCC voltage too low (UECPA=0x80000010)

**Hardware:** Qualcomm SM8150 (Snapdragon 855) — tested on Xiaomi Mi 9 (cepheus)  
**Kernel:** mainline 6.11 (sm8150-mainline)  
**Symptom:** UFS block device never appears; `dmesg` shows `UECPA=0x80000010`

---

## The problem

The SM8150 UFS M-PHY TX line requires VCC ≥ 2.95V. The `vreg_l10a_2p5` regulator
(PM8150 LDO10) in the device tree is typically defined with a wide voltage range
to accommodate other consumers:

```dts
vreg_l10a_2p5: ldo10 {
    regulator-min-microvolt = <2504000>;  /* ← too low */
    regulator-max-microvolt = <2960000>;
};
```

RPMh is free to program this rail anywhere in the `[min, max]` range. When it
chooses 2.504V, the UFS M-PHY TX activation timer (`T_TxActivate`) fires before
the PHY is ready, producing `UECPA=0x80000010` (PHY adapter error) on every
UFS command attempt. The block device never appears.

**`UECPA=0x80000010` is the diagnostic:** PHY error during UFS init, almost always
a power supply issue on Qualcomm platforms.

---

## The fix

Force the minimum voltage to match what the UFS M-PHY actually needs:

```dts
vreg_l10a_2p5: ldo10 {
    regulator-min-microvolt = <2950000>;  /* was 2504000 */
    regulator-max-microvolt = <2960000>;
};
```

After this change, RPMh programs VCC at 2.95V–2.96V, the PHY initialises
correctly, and the UFS device enumerates:

```
scsi host0: ufshcd
sd 0:0:0:0: [sda] 29655040 512-byte logical blocks: (15.2 GB/12.8 GiB)  
```

Rebuild the DTB and reflash or boot with the updated blob.

---

## Why the wide range exists

On the Mi 9, `vreg_l10a_2p5` supplies multiple peripherals at different voltages
across the boot lifecycle. The wide min–max was appropriate for the original
Android DTS where another driver claimed 2.5V before UFS needed 2.95V. On a
clean mainline DTS built specifically for storage, keeping the min at 2.504V is
a latent bug that surfaces whenever RPMh optimises for power.

---

## Vendor DTS reference

In MIUI/CAF kernels, the UFS power supply node carries explicit constraints:
```
vcc-voltage-level = <2950000 2960000>;
```
which clamps RPMh to the safe range. Mainline DTS files that omit this
and use a wide `regulator-min-microvolt` will hit this bug.

---

## Affected hardware

- SM8150 (Snapdragon 855) — confirmed
- Likely any Qualcomm platform where the UFS VCC regulator shares a rail with
  lower-voltage consumers and the DTS min-microvolt is set below 2.95V
