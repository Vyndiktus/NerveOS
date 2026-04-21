#!/bin/bash
K=/opt/NerveOS/build/cepheus/build/linux-cepheus-q-oss
DTS=$K/arch/arm64/boot/dts/qcom

echo "=== cepheus overlay structure (top-level nodes) ==="
grep -E "^&|^/ {|^\t[a-z].*{" $DTS/cepheus-sm8150-overlay.dts | head -50

echo "=== UFS in cepheus overlay ==="
grep -A10 "ufshc\|ufs" $DTS/cepheus-sm8150-overlay.dts | head -30

echo "=== Memory in cepheus overlay ==="
grep -A5 "memory\|mem_address\|reserved" $DTS/cepheus-sm8150-overlay.dts | head -20

echo "=== sm8150-v2.dts UFS node ==="
grep -n "ufshc\|1d84000" $DTS/sm8150-v2.dts | head -10
grep -n "ufshc\|1d84000" $DTS/sm8150.dtsi | head -10
