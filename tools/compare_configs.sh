#!/bin/bash
OUR=/opt/NerveOS/build/cepheus/build/linux-cepheus-q-oss/.config
REC=/mnt/c/Windows/Temp/recovery_config.txt

echo "=== CRITICAL: ARM64 VA bits and physical address ==="
echo "Ours:"
grep -E "^CONFIG_(ARM64_VA_BITS|PHYSICAL_START|PHYSICAL_ALIGN|RELOCATABLE|RANDOMIZE_BASE|KALLSYMS_BASE_RELATIVE|ARM64_PAGE_SHIFT|SHADOW_CALL_STACK|LTO|CFI_CLANG|CFI_PERMISSIVE)=" $OUR 2>/dev/null
echo "Recovery:"
grep -E "^CONFIG_(ARM64_VA_BITS|PHYSICAL_START|PHYSICAL_ALIGN|RELOCATABLE|RANDOMIZE_BASE|KALLSYMS_BASE_RELATIVE|ARM64_PAGE_SHIFT|SHADOW_CALL_STACK|LTO|CFI_CLANG|CFI_PERMISSIVE)=" $REC 2>/dev/null

echo ""
echo "=== QCOM early-init subsystems ==="
echo "Ours:"
grep -E "^CONFIG_(QCOM_SCM|QCOM_SMEM|QCOM_RPMH|MSM_PIL|QCOM_COMMAND_DB|QCOM_GLINK|QCOM_SMDPKT|QCOM_SMD|MSM_QMI_INTERFACE|QCOM_MDT_LOADER)=" $OUR 2>/dev/null
echo "Recovery:"
grep -E "^CONFIG_(QCOM_SCM|QCOM_SMEM|QCOM_RPMH|MSM_PIL|QCOM_COMMAND_DB|QCOM_GLINK|QCOM_SMDPKT|QCOM_SMD|MSM_QMI_INTERFACE|QCOM_MDT_LOADER)=" $REC 2>/dev/null

echo ""
echo "=== Memory model ==="
echo "Ours:"
grep -E "^CONFIG_(SPARSEMEM|SPARSEMEM_VMEMMAP|MEMORY_HOTPLUG|NUMA|NODES_SHIFT)=" $OUR 2>/dev/null
echo "Recovery:"
grep -E "^CONFIG_(SPARSEMEM|SPARSEMEM_VMEMMAP|MEMORY_HOTPLUG|NUMA|NODES_SHIFT)=" $REC 2>/dev/null

echo ""
echo "=== DRM and display ==="
echo "Ours: $(grep "^CONFIG_DRM=" $OUR)"
echo "Recovery: $(grep "^CONFIG_DRM=" $REC)"

echo ""
echo "=== Compiler/toolchain config ==="
echo "Ours:"
grep -E "^CONFIG_(CC_IS_GCC|CC_IS_CLANG|LTO_CLANG|GCC_PLUGINS)=" $OUR 2>/dev/null
echo "Recovery:"
grep -E "^CONFIG_(CC_IS_GCC|CC_IS_CLANG|LTO_CLANG|GCC_PLUGINS)=" $REC 2>/dev/null
