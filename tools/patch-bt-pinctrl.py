#!/usr/bin/env python3
"""Add BT UART pinctrl to sm8150-xiaomi-cepheus.dts"""
import sys

DTS = "/opt/NerveOS/build/cepheus/build/linux-4a8d88483/arch/arm64/boot/dts/qcom/sm8150-xiaomi-cepheus.dts"

with open(DTS) as f:
    content = f.read()

old = '\tdisp_vci_en_n: disp-vci-en-n-state {\n\t\tpins = "gpio88";\n\t\tfunction = "gpio";\n\t\tdrive-strength = <8>;\n\t\tbias-disable;\n\t};\n};'

new = '\tdisp_vci_en_n: disp-vci-en-n-state {\n\t\tpins = "gpio88";\n\t\tfunction = "gpio";\n\t\tdrive-strength = <8>;\n\t\tbias-disable;\n\t};\n\n\t/* BT UART (WCN3990) - qup13 = QUP2_SE3, GPIO 43-46 on SM8150 */\n\tqup_uart13_default: qup-uart13-default-state {\n\t\tpins = "gpio43", "gpio44", "gpio45", "gpio46";\n\t\tfunction = "qup13";\n\t\tdrive-strength = <2>;\n\t\tbias-disable;\n\t};\n};'

if old in content:
    content = content.replace(old, new, 1)
    with open(DTS, "w") as f:
        f.write(content)
    print("DTS updated successfully")
else:
    # Debug: show what we find around tlmm closing
    idx = content.find("disp_vci_en_n")
    print(f"Pattern not found. disp_vci_en_n at index {idx}")
    if idx >= 0:
        print(repr(content[idx:idx+200]))
    sys.exit(1)
