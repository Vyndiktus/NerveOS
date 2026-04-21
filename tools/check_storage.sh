#!/bin/bash
CFG=/opt/NerveOS/build/cepheus/build/linux-cepheus-q-oss/.config

echo "=== UFS (cepheus uses UFS storage) ==="
grep -E "^CONFIG_(SCSI_UFS|SCSI_UFSHCD|SCSI_UFSHCD_PLATFORM|SCSI_UFS_QCOM)" $CFG

echo "=== SCSI/block basics ==="
grep -E "^CONFIG_(SCSI|BLK_DEV_SD|BLK_DEV|PARTITION)" $CFG | head -15

echo "=== EXT4 ==="
grep -E "^CONFIG_EXT4" $CFG | head -5

echo "=== GPT/partition table ==="
grep -E "^CONFIG_(EFI_PARTITION|MSDOS_PARTITION|CMDLINE_PARTITION|PARTITION)" $CFG | head -10

echo "=== cmdline boot args ==="
grep "CONFIG_CMDLINE" $CFG | head -5

echo "=== USB_G_SERIAL in current config ==="
grep "USB_G_SERIAL" $CFG
