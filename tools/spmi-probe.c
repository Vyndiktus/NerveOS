// SPDX-License-Identifier: GPL-2.0-only
/*
 * spmi-probe.c — probe the two AP-accessible PM8150B peripherals:
 *   slave 2, 0x7200 (APID 120, owner=0)
 *   slave 2, 0xC600 (APID 126, owner=0)
 * Reads TYPE/SUBTYPE registers and reports, then tries a simple PWM enable
 * on 0x7200 to see if it makes the vibrator buzz.
 */
#include <linux/init.h>
#include <linux/module.h>
#include <linux/platform_device.h>
#include <linux/spmi.h>
#include <linux/regmap.h>
#include <linux/of.h>
#include <linux/slab.h>
#include <linux/delay.h>

/* Standard Qualcomm PMIC register offsets */
#define PERIPH_TYPE     0x04
#define PERIPH_SUBTYPE  0x05

/* LPG channel register offsets (if 0x7200 is LPG) */
#define LPG_PATTERN_CONFIG    0x40
#define LPG_PWM_SIZE_CLK      0x41
#define LPG_PWM_FREQ_PREDIV   0x42
#define LPG_PWM_TYPE_CONFIG   0x43
#define LPG_PWM_VALUE_LSB     0x44
#define LPG_PWM_VALUE_MSB     0x45
#define LPG_ENABLE_CONTROL    0x46
#define LPG_PWM_SYNC          0x47

static const struct regmap_config spmi_regmap_cfg = {
	.reg_bits = 16,
	.val_bits =  8,
	.max_register = 0xFFFF,
};

static int probe_peripheral(struct spmi_device *sdev,
			    u16 base, const char *name)
{
	struct regmap *map;
	unsigned int type = 0, subtype = 0;
	int ret;

	map = devm_regmap_init_spmi_ext(sdev, &spmi_regmap_cfg);
	if (IS_ERR(map)) {
		pr_err("spmi-probe: regmap init failed for %s: %ld\n",
		       name, PTR_ERR(map));
		return PTR_ERR(map);
	}

	ret = regmap_read(map, base + PERIPH_TYPE, &type);
	if (ret) {
		pr_err("spmi-probe: %s read TYPE failed: %d\n", name, ret);
		return ret;
	}
	regmap_read(map, base + PERIPH_SUBTYPE, &subtype);

	pr_info("spmi-probe: %s (0x%04X) TYPE=0x%02X SUBTYPE=0x%02X\n",
		name, base, type, subtype);

	/* If TYPE=0x0E (LPG), try to enable PWM to vibrate motor */
	if (type == 0x0E || type == 0x11) {
		pr_info("spmi-probe: %s looks like LPG — trying PWM buzz\n", name);

		/* Configure LPG for ~170Hz PWM, 50% duty cycle */
		/* PWM size=9bit, CLK=19.2MHz/2=9.6MHz */
		regmap_write(map, base + LPG_PATTERN_CONFIG, 0x00); /* no pattern */
		regmap_write(map, base + LPG_PWM_SIZE_CLK,   0x00); /* 6-bit, 1kHz */
		regmap_write(map, base + LPG_PWM_FREQ_PREDIV, 0x06); /* /64 */
		regmap_write(map, base + LPG_PWM_VALUE_LSB,  0x80); /* 50% duty */
		regmap_write(map, base + LPG_PWM_VALUE_MSB,  0x00);
		regmap_write(map, base + LPG_PWM_SYNC,       0x01); /* sync */
		regmap_write(map, base + LPG_ENABLE_CONTROL, 0xE4); /* enable output */

		pr_info("spmi-probe: %s PWM enabled — should buzz for 500ms\n", name);
		msleep(500);
		regmap_write(map, base + LPG_ENABLE_CONTROL, 0x00); /* disable */
		pr_info("spmi-probe: %s PWM disabled\n", name);
	}

	/* If TYPE=0x03 (GPIO), read the output state */
	if (type == 0x03) {
		unsigned int mode = 0;
		regmap_read(map, base + 0x45, &mode); /* GPIO mode/ctl */
		pr_info("spmi-probe: %s is GPIO, mode=0x%02X\n", name, mode);
	}

	return 0;
}

static int __init spmi_probe_init(void)
{
	struct device *dev;
	struct spmi_device *sdev;

	/* Find the PM8150B SPMI device (slave 2) */
	dev = bus_find_device_by_name(&spmi_bus_type, NULL, "0-02");
	if (!dev) {
		pr_err("spmi-probe: could not find SPMI device 0-02\n");
		return -ENODEV;
	}

	sdev = to_spmi_device(dev);
	pr_info("spmi-probe: found SPMI device %s\n", dev_name(dev));

	probe_peripheral(sdev, 0x7200, "periph_0x72");
	probe_peripheral(sdev, 0xC600, "periph_0xC6");

	put_device(dev);
	return 0;
}

static void __exit spmi_probe_exit(void)
{
}

module_init(spmi_probe_init);
module_exit(spmi_probe_exit);
MODULE_LICENSE("GPL v2");
MODULE_DESCRIPTION("SPMI peripheral probe for PM8150B AP-accessible peripherals");
