# Fix: panel-samsung-sofef00 DSI initialization ordering bug

**Affects:** Samsung EA8076 / s6e3fc2x01 AMOLED panel (Xiaomi Mi 9 `cepheus`, OnePlus 6 `enchilada`, OnePlus 6T `fajita`)  
**Kernel:** mainline `drivers/gpu/drm/panel/panel-samsung-sofef00.c`  
**Status:** Bug present in mainline as of kernel 6.11

---

## The bug

The sofef00 panel driver sends DSI DCS commands (exit sleep mode, display on, etc.) inside `sofef00_panel_prepare()`. In the DRM bridge pipeline, `drm_panel_prepare()` is called from `dsi_mgr_bridge_pre_enable()` — **before** the DSI PHY PLL is locked.

PHY PLL lock happens later, in `bridge_enable()`. Sending DCS commands over a lane clock that isn't running produces EINVAL (-22) from the DSI host controller and leaves the panel uninitialized.

### Call sequence (broken)

```
dsi_mgr_bridge_pre_enable()
  └─ drm_panel_prepare()
       └─ sofef00_panel_prepare()
            ├─ regulator_enable()
            ├─ sofef00_panel_reset()      ← GPIO reset: correct here
            └─ sofef00_panel_on()         ← DCS commands: WRONG, PHY PLL not locked yet

dsi_mgr_bridge_enable()
  └─ [PHY PLL locks here]
  └─ drm_panel_enable()                  ← not implemented, nothing called
```

### Symptoms

On a device with this panel and kernel 6.11 mainline:
- With DCS commands in `prepare()`: panel initialization fails silently or returns EINVAL, display never shows content. If `prepare()` returns 0 anyway, DRM enables the display and waits for a TE (Tear Effect) sync signal from a sleeping panel — **kernel hangs** before USB gadget or serial console initializes.
- No framebuffer content, no kernel panic, no obvious error without serial console attached.

---

## The fix

Split `prepare()` and `enable()` correctly:

- **`prepare()`** — regulator enable + GPIO reset only. These are safe before PHY lock.
- **`enable()`** (new callback) — all DCS commands. Called after PHY PLL is locked.

```c
static int sofef00_panel_prepare(struct drm_panel *panel)
{
	struct sofef00_panel *ctx = to_sofef00_panel(panel);
	struct device *dev = &ctx->dsi->dev;
	int ret;

	ret = regulator_enable(ctx->supply);
	if (ret < 0) {
		dev_err(dev, "Failed to enable regulator: %d\n", ret);
		return ret;
	}

	sofef00_panel_reset(ctx);

	return 0;
}

static int sofef00_panel_enable(struct drm_panel *panel)
{
	struct sofef00_panel *ctx = to_sofef00_panel(panel);
	struct device *dev = &ctx->dsi->dev;
	int ret;

	ret = sofef00_panel_on(ctx);
	if (ret < 0) {
		dev_err(dev, "Failed to initialize panel: %d\n", ret);
		return ret;
	}

	return 0;
}

static const struct drm_panel_funcs sofef00_panel_panel_funcs = {
	.prepare   = sofef00_panel_prepare,
	.enable    = sofef00_panel_enable,   /* add this line */
	.unprepare = sofef00_panel_unprepare,
	.get_modes = sofef00_panel_get_modes,
};
```

The `sofef00_panel_on()` function (which sends exit sleep, display on, and all init sequences) moves from `prepare()` to `enable()` unchanged.

---

## Related: Kconfig regression when enabling this driver

When adding `CONFIG_DRM_PANEL_SAMSUNG_SOFEF00=y` to a kernel config that also has `CONFIG_DRM_MSM=y`, running `make syncconfig` silently **demotes** `CONFIG_DRM_GEM_DMA_HELPER` from `=y` to `=m`.

Since `DRM_MSM=y` calls DMA helper functions at boot as a built-in, the missing symbol causes a kernel panic before any console output appears — indistinguishable from a boot hang.

**Workaround:** After any `syncconfig`, verify and re-assert:
```
CONFIG_DRM_GEM_DMA_HELPER=y
CONFIG_DRM_GEM_SHMEM_HELPER=y
```

This is a Kconfig dependency issue: `DRM_PANEL_SAMSUNG_SOFEF00` selects `DRM_GEM_DMA_HELPER` but with `depends on` logic that allows syncconfig to downgrade it when other options are in play.

---

## Tested on

| Device | SoC | Panel | Kernel | Result |
|--------|-----|-------|--------|--------|
| Xiaomi Mi 9 (cepheus) | SM8150 | Samsung EA8076 (s6e3fc2x01) | 6.11 sm8150-mainline | `/dev/fb0` working, framebuffer writes confirmed at 161 MB/s |

OnePlus 6 / 6T share the same panel and driver path and should benefit from the same fix, but were not tested directly.

---

## References

- Driver: `drivers/gpu/drm/panel/panel-samsung-sofef00.c`
- DRM bridge sequence: `drivers/gpu/drm/msm/dsi/dsi_manager.c` — `dsi_mgr_bridge_pre_enable()` / `dsi_mgr_bridge_enable()`
- sm8150-mainline kernel: https://github.com/sm8150-linux-mainline/linux
