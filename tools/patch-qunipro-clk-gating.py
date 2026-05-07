#!/usr/bin/env python3
"""
Add QUNIPRO DME clock-gating attribute writes to link_startup_notify(PRE_CHANGE).

Vendor ufs_qcom_enable_hw_clk_gating() sets four DME attributes for
hw_ver.major >= 3 (SM8150 = 4.1.0) before link startup:
  DL_VS_CLK_CFG    (0xA00B): DataLink VS clk gating enable
  PA_VS_CLK_CFG_REG (0x9004): PA VS clk gating enable
  DME_HW_CGC_EN    (bit 9 of DME_VS_CORE_CLK_CTRL 0xD002)
  SAVECONFIGTIME   (bits 13:14 of PA_VS_CONFIG_REG1 0x9000)

Mainline ufs_qcom_enable_hw_clk_gating() only sets REG_UFS_CFG2 and
misses all four QUNIPRO attributes. Without them, PA layer clock gating
is misconfigured and T_TxActivate may fail with PA_GENERIC_ERROR.

NOTE: DME_HW_CGC_EN is intentionally skipped in vendor for hw_ver==4.0.0
only. SM8150 is 4.1.0 (HW_VER=0x40010000), so it IS written.
"""
import sys

path = '/opt/nerveos/build/cepheus/build/linux-4a8d88483/drivers/ufs/host/ufs-qcom.c'
with open(path) as f:
    text = f.read()

old = (
    '\t\terr = ufs_qcom_set_core_clk_ctrl(hba, true);\n'
    '\t\tif (err)\n'
    '\t\t\tdev_err(hba->dev, "cfg core clk ctrl failed\\n");\n'
)

new = (
    '\t\terr = ufs_qcom_set_core_clk_ctrl(hba, true);\n'
    '\t\tif (err)\n'
    '\t\t\tdev_err(hba->dev, "cfg core clk ctrl failed\\n");\n'
    '\n'
    '\t\t/*\n'
    '\t\t * QUNIPRO DME clock-gating attributes (vendor enable_hw_clk_gating()).\n'
    '\t\t * Required for SM8150 (hw_ver.major >= 3 → 4.1.0). Mainline only sets\n'
    '\t\t * REG_UFS_CFG2; without these PA-layer clock gating is misconfigured\n'
    '\t\t * and T_TxActivate fails with UECPA=0x80000010 (PA_GENERIC_ERROR).\n'
    '\t\t */\n'
    '\t\t{\n'
    '\t\t\tu32 _dv;\n'
    '\n'
    '\t\t\t/* DL_VS_CLK_CFG 0xA00B: DataLink VS clk gating, all bits set */\n'
    '\t\t\tufshcd_dme_get(hba, UIC_ARG_MIB(0xA00B), &_dv);\n'
    '\t\t\tufshcd_dme_set(hba, UIC_ARG_MIB(0xA00B), _dv | 0x3FFU);\n'
    '\n'
    '\t\t\t/* PA_VS_CLK_CFG_REG 0x9004: PA VS clk gating, all bits set */\n'
    '\t\t\tufshcd_dme_get(hba, UIC_ARG_MIB(0x9004), &_dv);\n'
    '\t\t\tufshcd_dme_set(hba, UIC_ARG_MIB(0x9004), _dv | 0x1FFU);\n'
    '\n'
    '\t\t\t/* DME_HW_CGC_EN: bit 9 of DME_VS_CORE_CLK_CTRL 0xD002.\n'
    '\t\t\t * Vendor skips this only for hw_ver == 4.0.0; SM8150 is 4.1.0. */\n'
    '\t\t\tufshcd_dme_get(hba, UIC_ARG_MIB(DME_VS_CORE_CLK_CTRL), &_dv);\n'
    '\t\t\tufshcd_dme_set(hba, UIC_ARG_MIB(DME_VS_CORE_CLK_CTRL), _dv | BIT(9));\n'
    '\n'
    '\t\t\t/* SAVECONFIGTIME_MODE_MASK: bits 13:14 of PA_VS_CONFIG_REG1 0x9000 */\n'
    '\t\t\tufshcd_dme_get(hba, UIC_ARG_MIB(0x9000), &_dv);\n'
    '\t\t\tufshcd_dme_set(hba, UIC_ARG_MIB(0x9000), _dv | 0x6000U);\n'
    '\t\t}\n'
)

if old not in text:
    print('ERROR: target block not found — check current patch state')
    sys.exit(1)

text = text.replace(old, new, 1)
with open(path, 'w') as f:
    f.write(text)
print('link_startup_notify(PRE_CHANGE): QUNIPRO DME clk-gating attributes added OK')
