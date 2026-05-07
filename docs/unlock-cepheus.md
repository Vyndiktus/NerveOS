# Unlocking the Xiaomi Mi 9 (cepheus) Bootloader

Required before flashing NerveOS. **Wipers all data.**

## Prerequisites
- Windows PC (Mi Unlock Tool is Windows-only)
- Xiaomi account
- USB cable
- At least 7 days wait time after applying (Xiaomi enforces this)

## Steps

### 1. Apply for unlock permission
1. On the Mi 9: Settings → About Phone → tap MIUI Version 7 times (enables Developer Options)
2. Settings → Additional Settings → Developer Options → enable **OEM Unlocking**
3. Developer Options → enable **USB Debugging** and **Mi Unlock Status** → Add account and device

### 2. Download Mi Unlock Tool
- Download from: https://www.miui.com/unlock/download_en.html
- Sign in with your Xiaomi account

### 3. Wait
Xiaomi imposes a mandatory wait (typically 7 days). The app will tell you how many hours remain.

### 4. Unlock
1. Power off the Mi 9
2. Hold **Volume Down + Power** simultaneously until fastboot logo appears
3. Connect USB to PC
4. Open Mi Unlock Tool → click **Unlock**
5. Confirm the warning — device wipes and unlocks

### 5. Verify
```bash
fastboot getvar unlocked
# Expected output: unlocked: yes
```

## After Unlocking
Boot the device once into MIUI to confirm it works, then you're ready to flash NerveOS:

```bash
# Put device back into fastboot
# Power off → hold Vol- + Power

python tools/nerve-identify.py     # confirm device is detected
make flash DEVICE=cepheus          # flash NerveOS
```
