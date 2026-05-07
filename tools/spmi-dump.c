// SPDX-License-Identifier: GPL-2.0-only
/*
 * spmi-dump.c — reads SPMI arbiter APID map registers via /proc/driver/spmi_apid
 * Uses direct ioremap to read pmic_arb->core + 0x900 + 4*n (apid_map_offset_v5).
 * Also reads ownership from cnfg + 0x700 + 4*n.
 */
#include <linux/init.h>
#include <linux/module.h>
#include <linux/io.h>
#include <linux/proc_fs.h>
#include <linux/seq_file.h>

/* From /proc/iomem on SM8150:
 *   core:   0x0C440000, size 0x1100
 *   cnfg:   0x0C40A000, size 0x26000
 */
#define SPMI_CORE_BASE  0x0C440000UL
#define SPMI_CORE_SIZE  0x1200        /* slightly larger to cover 0x900+256*4=0xD00 */
#define SPMI_CNFG_BASE  0x0C40A000UL
#define SPMI_CNFG_SIZE  0x1000

#define APID_MAP_OFF    0x900         /* core + 0x900 + 4*n */
#define OWNERSHIP_OFF   0x700         /* cnfg + 0x700 + 4*n */
#define MAX_APID        256

static void __iomem *core_base;
static void __iomem *cnfg_base;

static int spmi_dump_show(struct seq_file *m, void *v)
{
	int i;
	u32 map_val, own_val;
	u16 ppid;
	u8 sid, periph, owner;

	if (!core_base || !cnfg_base) {
		seq_puts(m, "ioremap failed\n");
		return 0;
	}

	seq_printf(m, "APID  SID  PERIPH  OWNER  map_raw  own_raw\n");

	for (i = 0; i < MAX_APID; i++) {
		map_val = readl_relaxed(core_base + APID_MAP_OFF + i * 4);
		own_val = readl_relaxed(cnfg_base + OWNERSHIP_OFF + i * 4);

		if (!map_val)
			continue;

		ppid  = (map_val >> 8) & 0xFFF;
		sid   = (ppid >> 8) & 0xF;
		periph = ppid & 0xFF;
		owner  = own_val & 0x7;

		seq_printf(m, "%4d  %3d  0x%02X    %5d  0x%08X  0x%08X%s\n",
			   i, sid, periph, owner, map_val, own_val,
			   (sid == 2) ? "  <-- PM8150B" : "");
	}

	return 0;
}

static int spmi_dump_open(struct inode *inode, struct file *file)
{
	return single_open(file, spmi_dump_show, NULL);
}

static const struct proc_ops spmi_dump_ops = {
	.proc_open    = spmi_dump_open,
	.proc_read    = seq_read,
	.proc_lseek   = seq_lseek,
	.proc_release = single_release,
};

static int __init spmi_dump_init(void)
{
	core_base = ioremap(SPMI_CORE_BASE, SPMI_CORE_SIZE);
	if (!core_base) {
		pr_err("spmi-dump: ioremap core failed\n");
		return -ENOMEM;
	}

	cnfg_base = ioremap(SPMI_CNFG_BASE, SPMI_CNFG_SIZE);
	if (!cnfg_base) {
		iounmap(core_base);
		pr_err("spmi-dump: ioremap cnfg failed\n");
		return -ENOMEM;
	}

	proc_create("driver/spmi_apid", 0444, NULL, &spmi_dump_ops);
	pr_info("spmi-dump: /proc/driver/spmi_apid ready\n");
	return 0;
}

static void __exit spmi_dump_exit(void)
{
	remove_proc_entry("driver/spmi_apid", NULL);
	if (core_base) iounmap(core_base);
	if (cnfg_base) iounmap(cnfg_base);
}

module_init(spmi_dump_init);
module_exit(spmi_dump_exit);
MODULE_LICENSE("GPL v2");
MODULE_DESCRIPTION("SPMI arbiter APID map dump");
