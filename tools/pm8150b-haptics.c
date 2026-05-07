// SPDX-License-Identifier: GPL-2.0-only
/*
 * Minimal LRA haptics driver for Qualcomm PM8150B PMIC.
 *
 * Register map (offsets from SPMI base, typically 0xDE00):
 *   +0x46  HAP_EN_CTL1  bit7 = actuator enable
 *   +0x4C  HAP_CFG1     bit0 = actuator type (0=ERM, 1=LRA)
 *   +0x4E  HAP_SEL      play mode  (0=buffer, 1=direct, 2=audio, 3=pwm)
 *   +0x51  HAP_VMAX     bits[5:1] = amplitude in 116mV steps from 116mV
 *   +0x54  HAP_RATE1    bits[3:0] = LRA period upper nibble (5µs/step)
 *   +0x55  HAP_RATE2    bits[7:0] = LRA period lower byte
 *   +0x60  HAP_WAVE     0 = sine, 1 = square
 *   +0x70  HAP_PLAY     bit7 = play enable
 *
 * Exposes both:
 *  - input FF_RUMBLE interface (for apps)
 *  - sysfs duration/activate (for shell testing)
 *
 * Each Qualcomm SPMI peripheral driver owns its own regmap initialised via
 * devm_regmap_init_spmi_ext() — do NOT use dev_get_regmap(parent).
 */
#include <linux/errno.h>
#include <linux/hrtimer.h>
#include <linux/input.h>
#include <linux/kernel.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/platform_device.h>
#include <linux/regmap.h>
#include <linux/slab.h>
#include <linux/spmi.h>

#define HAP_EN_CTL1   0x46
#define HAP_CFG1      0x4C
#define HAP_SEL       0x4E
#define HAP_VMAX      0x51
#define HAP_RATE1     0x54
#define HAP_RATE2     0x55
#define HAP_WAVE      0x60
#define HAP_PLAY      0x70

#define HAP_EN_BIT    BIT(7)
#define HAP_PLAY_BIT  BIT(7)
#define HAP_LRA_TYPE  BIT(0)
#define HAP_DIRECT    0x01

#define HAP_RATE_STEP_US   5       /* 5µs per rate register step */
#define HAP_VMAX_BASE_MV   116
#define HAP_VMAX_STEP_MV   116

struct pm8150b_hap {
	struct input_dev  *idev;
	struct regmap     *regmap;
	u32                base;
	struct work_struct work;
	struct hrtimer     timer;
	bool               active;
	u32                duration_ms;
};

static void hap_reg_write(struct pm8150b_hap *h, unsigned int off, u8 val)
{
	int ret = regmap_write(h->regmap, h->base + off, val);
	if (ret)
		pr_err("pm8150b-haptics: regmap write +0x%02x failed: %d\n",
		       off, ret);
}

static void hap_start(struct pm8150b_hap *h)
{
	hap_reg_write(h, HAP_EN_CTL1, HAP_EN_BIT);
	hap_reg_write(h, HAP_PLAY, HAP_PLAY_BIT);
}

static void hap_stop(struct pm8150b_hap *h)
{
	hap_reg_write(h, HAP_PLAY, 0);
	hap_reg_write(h, HAP_EN_CTL1, 0);
}

static void hap_work_fn(struct work_struct *work)
{
	struct pm8150b_hap *h = container_of(work, struct pm8150b_hap, work);
	if (h->active)
		hap_start(h);
	else
		hap_stop(h);
}

static enum hrtimer_restart hap_timer_fn(struct hrtimer *t)
{
	struct pm8150b_hap *h = container_of(t, struct pm8150b_hap, timer);
	h->active = false;
	schedule_work(&h->work);
	return HRTIMER_NORESTART;
}

/* ── FF_RUMBLE interface ─────────────────────────────────────────────────── */

static int hap_ff_play(struct input_dev *dev, void *data,
		       struct ff_effect *effect)
{
	struct pm8150b_hap *h = input_get_drvdata(dev);
	u16 mag = max(effect->u.rumble.strong_magnitude,
		      effect->u.rumble.weak_magnitude);

	hrtimer_cancel(&h->timer);

	if (mag == 0) {
		h->active = false;
	} else {
		u32 ms = effect->replay.length ?: 100;
		h->active = true;
		hrtimer_start(&h->timer, ms_to_ktime(ms), HRTIMER_MODE_REL);
	}
	schedule_work(&h->work);
	return 0;
}

/* ── Sysfs interface ─────────────────────────────────────────────────────── */

static ssize_t activate_store(struct device *dev,
		struct device_attribute *attr, const char *buf, size_t count)
{
	struct pm8150b_hap *h = dev_get_drvdata(dev);
	unsigned int val;

	if (kstrtouint(buf, 10, &val))
		return -EINVAL;

	hrtimer_cancel(&h->timer);
	h->active = !!val;
	if (h->active && h->duration_ms)
		hrtimer_start(&h->timer, ms_to_ktime(h->duration_ms),
			      HRTIMER_MODE_REL);
	schedule_work(&h->work);
	return count;
}

static ssize_t duration_store(struct device *dev,
		struct device_attribute *attr, const char *buf, size_t count)
{
	struct pm8150b_hap *h = dev_get_drvdata(dev);
	if (kstrtouint(buf, 10, &h->duration_ms))
		return -EINVAL;
	return count;
}

static ssize_t duration_show(struct device *dev,
		struct device_attribute *attr, char *buf)
{
	struct pm8150b_hap *h = dev_get_drvdata(dev);
	return sysfs_emit(buf, "%u\n", h->duration_ms);
}

static DEVICE_ATTR_WO(activate);
static DEVICE_ATTR_RW(duration);

static struct attribute *hap_attrs[] = {
	&dev_attr_activate.attr,
	&dev_attr_duration.attr,
	NULL,
};
ATTRIBUTE_GROUPS(hap);

static const struct regmap_config hap_regmap_config = {
	.reg_bits = 16,
	.val_bits =  8,
	.max_register = 0xFFFF,
};

/* ── Probe ───────────────────────────────────────────────────────────────── */

static int pm8150b_hap_probe(struct platform_device *pdev)
{
	struct pm8150b_hap *h;
	struct input_dev   *idev;
	struct spmi_device *sdev;
	u32 base, period_us = 5882, vmax_mv = 1800;
	u16 rate_code;
	u8  vmax_code;
	int ret;

	h = devm_kzalloc(&pdev->dev, sizeof(*h), GFP_KERNEL);
	if (!h)
		return -ENOMEM;

	ret = of_property_read_u32(pdev->dev.of_node, "reg", &base);
	if (ret) {
		dev_err(&pdev->dev, "missing reg property\n");
		return ret;
	}
	h->base = base;

	/* Each SPMI peripheral driver owns its own regmap via spmi_ext */
	sdev = to_spmi_device(pdev->dev.parent);
	h->regmap = devm_regmap_init_spmi_ext(sdev, &hap_regmap_config);
	if (IS_ERR(h->regmap)) {
		dev_err(&pdev->dev, "regmap init failed: %ld\n",
			PTR_ERR(h->regmap));
		return PTR_ERR(h->regmap);
	}

	of_property_read_u32(pdev->dev.of_node, "qcom,lra-period-us", &period_us);
	of_property_read_u32(pdev->dev.of_node, "qcom,vmax-mv",       &vmax_mv);

	rate_code = (u16)(period_us / HAP_RATE_STEP_US);
	vmax_code = (u8)clamp_t(u32, (vmax_mv - HAP_VMAX_BASE_MV) / HAP_VMAX_STEP_MV,
				0, 31);

	/* Probe the two AP-accessible slave-2 peripherals to identify them */
	{
		unsigned int type = 0, sub = 0;
		if (regmap_read(h->regmap, 0x7204, &type) == 0 &&
		    regmap_read(h->regmap, 0x7205, &sub) == 0)
			dev_info(&pdev->dev,
				 "periph 0x72: TYPE=0x%02X SUBTYPE=0x%02X\n",
				 type, sub);
		else
			dev_info(&pdev->dev, "periph 0x72: read failed\n");

		type = 0; sub = 0;
		if (regmap_read(h->regmap, 0xC604, &type) == 0 &&
		    regmap_read(h->regmap, 0xC605, &sub) == 0)
			dev_info(&pdev->dev,
				 "periph 0xC6: TYPE=0x%02X SUBTYPE=0x%02X\n",
				 type, sub);
		else
			dev_info(&pdev->dev, "periph 0xC6: read failed\n");
	}

	/* Static LRA configuration */
	hap_reg_write(h, HAP_CFG1,  HAP_LRA_TYPE);
	hap_reg_write(h, HAP_SEL,   HAP_DIRECT);
	hap_reg_write(h, HAP_VMAX,  (vmax_code << 1) & 0x3E);
	hap_reg_write(h, HAP_RATE1, (rate_code >> 8) & 0x0F);
	hap_reg_write(h, HAP_RATE2, rate_code & 0xFF);
	hap_reg_write(h, HAP_WAVE,  0x00);   /* sine */

	INIT_WORK(&h->work, hap_work_fn);
	hrtimer_init(&h->timer, CLOCK_MONOTONIC, HRTIMER_MODE_REL);
	h->timer.function = hap_timer_fn;
	h->duration_ms    = 100;

	/* Input device for FF_RUMBLE */
	idev = devm_input_allocate_device(&pdev->dev);
	if (!idev)
		return -ENOMEM;
	h->idev = idev;

	idev->name    = "pm8150b-haptics";
	idev->id.bustype = BUS_HOST;
	input_set_drvdata(idev, h);
	input_set_capability(idev, EV_FF, FF_RUMBLE);

	ret = input_ff_create_memless(idev, NULL, hap_ff_play);
	if (ret)
		return ret;

	ret = input_register_device(idev);
	if (ret)
		return ret;

	platform_set_drvdata(pdev, h);

	dev_info(&pdev->dev,
		 "PM8150B LRA haptics: %u Hz, %u mV\n",
		 1000000 / period_us, vmax_mv);
	return 0;
}

static void pm8150b_hap_remove(struct platform_device *pdev)
{
	struct pm8150b_hap *h = platform_get_drvdata(pdev);
	hrtimer_cancel(&h->timer);
	cancel_work_sync(&h->work);
	hap_stop(h);
}

static const struct of_device_id pm8150b_hap_of_match[] = {
	{ .compatible = "qcom,pm8150b-haptics" },
	{ }
};
MODULE_DEVICE_TABLE(of, pm8150b_hap_of_match);

static struct platform_driver pm8150b_hap_driver = {
	.probe  = pm8150b_hap_probe,
	.remove = pm8150b_hap_remove,
	.driver = {
		.name           = "pm8150b-haptics",
		.of_match_table = pm8150b_hap_of_match,
		.dev_groups     = hap_groups,
	},
};
module_platform_driver(pm8150b_hap_driver);

MODULE_DESCRIPTION("Qualcomm PM8150B LRA haptics driver");
MODULE_LICENSE("GPL v2");
MODULE_AUTHOR("NerveOS");
