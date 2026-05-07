# NerveOS — Project Intelligence Document

This file is automatically loaded by Claude Code. Keep it updated after every significant session.
Last updated: 2026-05-04 (session 24 — Audio deep debug; WCD9340 EAR+LINEOUT PAs working; speaker needs QUAT MI2S + CS35L41 driver)

---

## What Is NerveOS

NerveOS is a custom Linux-based operating system — not Android, not a distro fork — inspired by the networked OS in the film *Antitrust* (2001). The core concept: every device running NerveOS is a node in an encrypted peer-to-peer mesh. Nodes automatically discover each other and pool their CPU, RAM, and storage into a collective resource layer called "the hive."

**Guiding principles:**
- AI-native at every layer (OS-level LLM context, semantic resource scheduling — future work)
- Universal: one codebase, images for phones, SBCs, PCs, embedded devices
- Encrypted by default: all inter-node communication over WireGuard tunnels
- No central authority: fully distributed discovery and resource brokering

---

## Path Notes

- **Shell CWD resets to:** `c:\Users\Forbidden User` (home dir) after each Bash call
- **Project root:** `NerveOS/` relative to home = `C:\Users\Forbidden User\NerveOS\`
- **Always use `NerveOS/` prefix** in relative paths from bash, or full Windows paths in Write/Edit/Read tools

## Repository Layout

```
NerveOS/                              ← project root (C:\Users\Forbidden User\NerveOS\)
├── CLAUDE.md                        ← you are here
├── Makefile                         ← top-level orchestration
├── devices/                         ← device profiles (one YAML per device)
│   └── cepheus.yaml                 ← Xiaomi Mi 9
├── br2-external/                    ← Buildroot external tree (never modify Buildroot itself)
│   ├── external.desc
│   ├── external.mk
│   ├── Config.in
│   ├── board/
│   │   └── cepheus/
│   │       ├── post-build.sh        ← runs after rootfs assembly
│   │       └── hived.conf.default   ← default config copied to /etc/hive/hived.conf
│   ├── configs/
│   │   └── NerveOS_cepheus_defconfig ← Buildroot config for Mi 9
│   └── package/
│       └── hived/                   ← Buildroot package definition for hived
│           ├── Config.in
│           ├── hived.mk
│           └── hived.init           ← SysV init script → /etc/init.d/S99hived
├── hived/                           ← Hive daemon (Go)
│   ├── go.mod                       ← module: NerveOS/hived
│   ├── cmd/hived/
│   │   ├── main.go                  ← entry point, wires up subsystems
│   │   └── config.go                ← TOML config loading, node identity
│   └── internal/
│       ├── mesh/mesh.go             ← WireGuard interface + peer management
│       ├── discovery/discovery.go   ← mDNS (local) + DHT (internet) peer discovery
│       └── resources/resources.go  ← CPU/RAM/storage advertisement + brokering
├── tools/
│   ├── hive-identify.py             ← USB device identifier (fastboot + adb)
│   └── hive-flash.py                ← Image flasher via fastboot
├── rootfs-overlay/                  ← Files dropped into every device's rootfs
│   ├── etc/hive/                    ← Runtime config dir (keys, certs, hived.conf)
│   └── usr/bin/hive                 ← User-facing CLI shim
├── docs/
│   └── unlock-cepheus.md            ← Mi 9 bootloader unlock guide
└── build/                           ← Generated (gitignored)
    ├── <device>/                    ← Buildroot output tree
    └── images/<device>/             ← Final flashable images
```

---

## Key Technical Decisions (and why)

| Decision | Choice | Reason |
|----------|--------|--------|
| Build system | **Buildroot** | Faster iteration than Yocto; Yocto is overkill until we have 5+ device targets |
| Hive daemon language | **Go** | Excellent ARM64 cross-compilation (`GOOS=linux GOARCH=arm64`), strong networking/concurrency primitives |
| Mesh VPN | **WireGuard** | Kernel-integrated, minimal attack surface, low overhead — perfect for phones |
| Peer discovery | **mDNS + DHT** | mDNS for LAN (zero config), DHT for internet-wide discovery without a central server |
| Init system | **SysV** (busybox) | Simplest for embedded; can migrate to OpenRC or systemd later |
| Config format | **TOML** | Simple, readable, good Go library support |

---

## Device Registry

### cepheus — Xiaomi Mi 9
- **File:** `devices/cepheus.yaml`
- **SoC:** Qualcomm Snapdragon 855 (SM8150), ARM64
- **RAM:** 6GB (base) / 8GB
- **Kernel source:** https://github.com/MiCode/Xiaomi_Kernel_OpenSource branch `cepheus-q-oss`
- **Bootloader:** Qualcomm ABL — requires Mi Unlock Tool (Windows), ~7 day wait
- **Status:** Profile written, defconfig written, not yet built or flashed
- **Unlock guide:** `docs/unlock-cepheus.md`
- **Flash command:** `make flash DEVICE=cepheus`
- **USB detection:** `python tools/hive-identify.py`

**Firmware blobs required (proprietary, not in repo):**
- Extract from stock MIUI ROM: `lib/firmware/qcom/sm8150/`, `lib/firmware/wlan/qca_cld3/`

---

## hived Architecture

```
hived (PID 1 or init.d S99)
├── mesh.Manager        — owns WireGuard interface "hive0", peer add/remove
├── discovery.Manager   — mDNS announcer/scanner + DHT announcer/lookup
│                         → calls mesh.Manager.AddPeer() when new peers found
└── resources.Manager   — samples CPU/RAM/storage every 10s
                          → broadcasts Advertisement to peers (future: via hive protocol)
```

**WireGuard interface:** `hive0`, listen port `51820`
**Config location on device:** `/etc/hive/hived.conf`
**Key location on device:** `/etc/hive/wg-private.key` (generated on first boot)

### What's implemented (as of 2026-04-18)
- **`mesh/keys.go`**: WireGuard keypair generation via `wg genkey/pubkey`, persisted to `/etc/hive/wg-private.key`
- **`mesh/hiveip.go`**: Deterministic hive IP (`10.42.x.x`) derived from first 2 bytes of node ID
- **`mesh/mesh.go`**: Full WireGuard interface lifecycle — key loading, IP assignment, peer add/remove with route injection
- **`discovery/discovery.go`**: Real mDNS via `github.com/grandcat/zeroconf` — announces node (pubkey, hive IP, WG port in TXT), browses for peers every 30s, adds discovered peers to mesh. Static peer bootstrap via `pubkey@host:port` config entries.
- **`resources/resources.go`**: Real `/proc/meminfo` RAM sampling, `/proc/stat` CPU delta sampling, `syscall.Statfs` storage sampling — all with configurable reserves applied

### Transport layer (added 2026-04-18, Haven integration)
- **`transport/transport.go`**: Transport type enum (WiFi, Batman, HaLow, Reticulum, LoRa, Ethernet) + DiscoveryMode
- **`transport/detector.go`**: Runtime scanner — reads `net.Interfaces()`, classifies by name, ranks by hive preference (batman > halow > wifi > ethernet > reticulum), exposes `MDNSIfaces()` and `HasReticulum()`
- **`transport/reticulum.go`**: RNSAnnouncer — announces node identity over Reticulum, discovers `NerveOS.node` destinations via `rnpath`. Uses one-shot Python3 subprocess until a native Go RNS socket client is implemented.
- **`discovery/discovery.go`**: Now transport-aware — binds mDNS to detected WiFi/batman interfaces, starts RNSAnnouncer when Reticulum is available. mDNS over `bat0` works transparently — propagates across the entire BATMAN-adv mesh.

### Buildroot transport stack (added 2026-04-18)
- `batctl` package added to defconfig
- `kernel-batman.config` fragment: `CONFIG_BATMAN_ADV=m`, `CONFIG_MAC80211_MESH=y`
- `python-rns` Buildroot package: Reticulum 1.1.6 from PyPI
- `S50batman` init script: sets up 802.11s mesh point on `wlan*`, adds to `bat0`, starts DHCP on bat0
- `S60reticulum` init script: starts `rnsd` with `/etc/reticulum/config`
- Reticulum config: AutoInterface (LAN multicast) + batman-adv binding + disabled TCP bootstrap (enable when bootstrap.NerveOS.network is deployed) + disabled LoRa (enable when hardware added)

### Haven integration summary
- **BATMAN-adv** (`bat0`): unified L2 mesh over all 802.11s-capable WiFi interfaces. Multi-hop, self-healing. mDNS works natively across the mesh.
- **Reticulum**: encrypted overlay for long-range/LoRa discovery. Runs on top of batman-adv or directly over WiFi.
- **HaLow (802.11ah)**: flagged in device profile as hardware-dependent. When a Morse Micro adapter is present, it appears as a WiFi interface and is auto-added to batman-adv.
- **Haven subnet**: `10.41.x.x/16` — no conflict with NerveOS WG subnet `10.42.x.x/16`

### WiFi + Bluetooth (session 8 — 2026-04-21)

**Hardware:** Qualcomm WCN3990 combo chip — handles both WiFi (802.11a/b/g/n/ac) and BT 5.0

**DTS changes in `sm8150-xiaomi-cepheus.dts`:**
- `aliases`: added `bluetooth0 = &bluetooth; wifi0 = &wifi;`
- `&wifi` node enabled with power supplies: `vdd-0.8-cx-mx` (vreg_l1a_0p75), `vdd-1.8-xo` (vreg_l7a_1p8), `vdd-1.3-rfa` (vreg_l2c_1p3), `vdd-3.3-ch0` (vreg_l11c_3p3)
- `&uart13` enabled with `bluetooth` child: `compatible = "qcom,wcn3990-bt"`, `vddio` (vreg_l12a_1p8), `vddxo` (vreg_l7a_1p8), `vddrf` (vreg_l2c_1p3), `vddch0` (vreg_l11c_3p3), `max-speed = <3200000>`

**Kernel config additions (`kernel-nerveos-mainline.config`):**
- WiFi: `CONFIG_CFG80211=y`, `CONFIG_MAC80211=y`, `CONFIG_ATH10K=y`, `CONFIG_ATH10K_SNOC=y`
- BT: `CONFIG_BT=y`, `CONFIG_BT_HCIUART=y`, `CONFIG_BT_HCIUART_QCA=y`, `CONFIG_BT_QCA=y`

**Firmware required (not in repo):**
- WiFi: `/lib/firmware/ath10k/WCN3990/hw1.0/firmware-5.bin` + `board-2.bin` (from linux-firmware.git)
- BT: Loaded via AMSS PIL — needs wcnss firmware blobs from MIUI ROM extraction

**BATMAN-adv mesh plan:**
- WiFi (`wlan0`) → 802.11s mesh point → `bat0` interface
- Bluetooth PAN (`bnep0`) → also added to `bat0`
- Both transports feed into unified L2 mesh, mDNS propagates across entire mesh

**Boot image `v31`** (`/opt/boot_nerveos_v31.img`): updated DTB with WiFi/BT nodes + mdev-d fix. Current kernel lacks ATH10K_SNOC/BT_HCIUART_QCA (built before config update) — hardware will probe/fail gracefully. Full WiFi/BT functional after Buildroot kernel rebuild.

### What's still stubbed / not yet implemented
- **RNS socket client**: `transport/reticulum.go` uses Python subprocess — needs native Go socket protocol
- **DHT**: Static peer bootstrap only — full DHT future work
- **`hive` CLI**: `join` and `status` are stubs
- **Inter-node protocol**: Nodes connect over WireGuard but don't yet exchange resource advertisements or assign work
- **CPU offload / RAM sharing / distributed storage**: All future milestones
- **HaLow auto-detection**: When a HaLow adapter is plugged in, udev rules needed to name it `halow0` and add to batman-adv

---

## Build Workflow

### Prerequisites (host machine) — ALL INSTALLED ✅
- **WSL2 Debian** — upgraded from WSL1, all build deps installed (2026-04-18)
  - `aarch64-linux-gnu-gcc 14.2.0`, `make 4.4.1`, `python3 3.13`, `git 2.47`
  - Project accessible inside WSL2 at `/mnt/c/Users/Forbidden User/NerveOS`
  - Run Buildroot builds as: `wsl -d Debian -u root -- make -C /mnt/c/Users/Forbidden\ User/NerveOS DEVICE=cepheus`
- **fastboot 37.0.0 + adb 1.0.41** — Android platform-tools, in PATH on Windows
- **Python 3.14.3** — with `pyyaml 6.0.3` installed
- **Go 1.26.2** — installed via winget, available in PATH

### Commands
```bash
make setup                  # Clone Buildroot 2024.02
make DEVICE=cepheus         # Full build (takes 1-2 hours first time)
make flash DEVICE=cepheus   # Flash to connected device
make identify               # Identify USB-connected devices
make identify-watch         # Watch for device connections continuously
make hived                  # Build hived natively (for testing)
make hived-arm64            # Cross-compile hived for ARM64
```

### Adding a new device
1. Create `devices/<codename>.yaml` (copy cepheus.yaml as template)
2. Create `br2-external/board/<codename>/` with `post-build.sh` and `hived.conf.default`
3. Create `br2-external/configs/NerveOS_<codename>_defconfig`
4. Run `make DEVICE=<codename>`

---

## Kernel Build — Patches Applied (cepheus-q-oss + GCC 14 + Bootlin toolchain)

These 6 patches in `br2-external/board/cepheus/linux-patches/` solve all kernel build failures:

| Patch | Fix |
|-------|-----|
| `0001-fix-gcc-wrapper-python3.patch` | gcc-wrapper.py: Python 3 compat + make interpret_warning a no-op |
| `0002-disable-rticdata-section.patch` | `__rticdata` → no-op in `init.h` (R_AARCH64_ADR_PREL_PG_HI21 relocation overflow) |
| `0003-disable-kaslr-defconfig.patch` | `cepheus_user_defconfig`: `CONFIG_RANDOMIZE_BASE=n` (silentoldconfig restores it from defconfig; fragment alone insufficient) |
| `0004-remove-sde-rot-from-drm-makefile.patch` | Remove `sde_hw_rot.o` from DRM Makefile (depends on SDE rotator which we disable) |
| `0005-thermal-guard-drm-msm-notifier.patch` | `thermal_core.c`: change `#ifdef CONFIG_DRM` → `#ifdef CONFIG_DRM_MSM` for drm_register_client calls |
| `0006-kallsyms-no-base-relative.patch` | `init/Kconfig`: `KALLSYMS_BASE_RELATIVE` default `n` — promptless bool, can't be overridden by fragment |

Key config fragment additions (`kernel-NerveOS.config`):
- `CONFIG_DRM=n` — entire DRM/display disabled (Qualcomm's drm_sysfs.c calls MSM-specific symbols; NerveOS is headless)
- `CONFIG_RANDOMIZE_BASE=n` — also in fragment (belt and suspenders with patch 0003)
- `CONFIG_KALLSYMS_BASE_RELATIVE=n` — in fragment (belt and suspenders with patch 0006)
- All previous: QCOM_MDSS_PLL, MSM_RDBG, QCOM_KGSL, HID_QVR, SPECTRA_CAMERA, MSM_SDE_ROTATOR, IPA3, RNDIS_IPA, GSI, IDT_P9220

### WSL2 build environment
- Build script: `/opt/NerveOS-build.sh` (Windows: `NerveOS/NerveOS-build.sh`)
- Build output: `/opt/NerveOS/build/cepheus/`
- Build log: `/opt/NerveOS/build/cepheus/build.log`
- Launch: `Start-Process -FilePath 'wsl.exe' -ArgumentList '-d','Debian','-u','root','bash','/opt/NerveOS-build.sh' -WindowStyle Hidden`
- Proxmox token: stored in WSL2 `~/.config/NerveOS/proxmox.env`
- NerveOS-dev-01 container: Debian 12 LXC on Proxmox (SSH alias `NerveOS-dev-01`)

### IMPORTANT: Stamp management for incremental kernel builds
When Buildroot stops mid-kernel-build and you need to apply a fix:
- `rm .stamp_built` → forces kernel rebuild (compilation cached, only affected objects recompile)
- `rm .stamp_built .stamp_configured .stamp_kconfig_fixup_done .stamp_dotconfig` → forces full kernel reconfigure + rebuild
- NEVER `rm .stamp_patched` without also re-applying patches manually (Buildroot detects duplicates and errors)
- Patches 0001-0006 are already applied to the extracted source in WSL2; they only re-apply on fresh extract

---

## Current Status (as of 2026-04-18, session 2)

### Done
- [x] Full project scaffold and directory structure
- [x] cepheus device profile (`devices/cepheus.yaml`)
- [x] Buildroot external tree (`br2-external/`)
- [x] Buildroot defconfig for cepheus (ARM64, WireGuard, Go, hived)
- [x] `hive-identify.py` — USB identification tool
- [x] `hive-flash.py` — Fastboot flasher with safety checks
- [x] `hived` Go daemon skeleton (mesh, discovery, resources)
- [x] `hive` CLI shim in rootfs overlay
- [x] Bootloader unlock documentation for cepheus
- [x] **Bootloader unlocked** on physical Mi 9
- [x] **Kernel builds successfully** — vmlinux linked, Image.gz generated (session 2)
- [x] NerveOS-dev-01 LXC container on Proxmox — hived tested and running
- [x] Proxmox API token configured

### Mainline kernel boot — session 3 (2026-04-19)

**Working boot image:** `/opt/boot_static.img` (copied to `C:\Windows\Temp\NerveOS_boot_static.img`)
- Kernel: `Image-mainline-nokaslr.gz` (6.11, from sm8150-mainline) + `sm8150-xiaomi-cepheus.dtb`
- Cmdline: `nomodeset clk_ignore_unused pd_ignore_unused console=tty0 console=ttyMSM0,115200n8 earlycon=qcom_geni,0xa90000 loglevel=8 rdinit=/init`
- Ramdisk: static busybox initramfs with USB ACM gadget setup
- **Always run `fastboot erase dtbo` before booting mainline**

**USB serial shell confirmed working:**
- UDC: `a600000.usb` (DWC3 peripheral, USB 2.0 HS)
- COM3 on host (115200 baud, auto-login to /bin/sh)
- Kernel version: Linux 6.11.0-sm8150-g4a8d8848356e
- RAM: 5.5 GB available

**Key DTS fixes in `sm8150-xiaomi-cepheus.dts`:**
- `usb_1`: added `qcom,select-utmi-as-pipe-clk` (USB 2.0 only, Mi 9 has no USB 3)
- `usb_1_dwc3`: overridden `phys = <&usb_1_hsphy>; phy-names = "usb2-phy";` (drop QMP PHY from USB)
- `usb_1_qmpphy`: kept **enabled** with supplies — needed for DRM DisplayPort path (`mdss_dp_out`)
- `nomodeset clk_ignore_unused pd_ignore_unused` required to keep simple-framebuffer alive

**Key boot lesson:** DWC3 peripheral probes ~5s after userspace starts (deferred probe). Init must wait for `/sys/class/udc/` to appear before trying to bind the gadget.

### UFS fix history (session 4 — 2026-04-21)

**Fix32 — VCC voltage (SOLVED UFS block device init):**
- Root cause: `vreg_l10a_2p5` (PM8150 L10) `regulator-min-microvolt = <2504000>` allowed RPMh to program VCC at 2.504V. UFS M-PHY TX requires VCC ≥2.95V (vendor: `vcc-voltage-level = <2950000 2960000>`). At 2.504V, T_TxActivate timer fired → UECPA=0x80000010 on every attempt.
- Fix: Changed min-microvolt to 2950000 in `sm8150-xiaomi-cepheus.dts`. DTB rebuilt via `cpp` + `dtc` directly (kernel make target has doubled-path bug).
- Result: WD SDINDDH4-128G (128GB) enumerated as `sda` with 29,655,040 × 4096-byte blocks, all 31 partitions visible. **UFS is fully working.**

**DTB rebuild workaround** (kernel make doubled-path bug):
```bash
cpp -nostdinc -undef -D__DTS__ -x assembler-with-cpp \
  -I $K/include -I $K/arch/arm64/boot/dts -I $K/arch/arm64/boot/dts/qcom \
  -o /tmp/cepheus.dts.tmp $K/arch/arm64/boot/dts/qcom/sm8150-xiaomi-cepheus.dts
/usr/bin/dtc -O dtb -b 0 -W no-unit_address_vs_reg \
  -i $K/arch/arm64/boot/dts/qcom -i $K/arch/arm64/boot/dts \
  -o $K/arch/arm64/boot/dts/qcom/sm8150-xiaomi-cepheus.dtb /tmp/cepheus.dts.tmp
```

### sysvinit getty fix — session 5 (2026-04-21)

**Problem:** sysvinit (real sysvinit 47KB binary, NOT busybox init) silently skipped `::respawn:` entries with empty id fields. Also, `exec /sbin/getty` wrapper exited when getty died, triggering sysvinit's respawn-too-fast backoff (60s).

**Fix applied to `/dev/sda31` rootfs:**
- `/sbin/ttygs0_init.sh`: looping wrapper (`while true; do /sbin/getty -L -n -l /bin/sh 115200 ttyGS0; sleep 5; done`) — never exits, prevents respawn-too-fast
- `/etc/inittab`: `GS0::respawn:/sbin/ttygs0_init.sh` — valid 3-char sysvinit id (sysvinit id field is 1–4 chars identifier only, NOT the tty name)
- `/etc/init.d/rcS`: `echo "HIVEOS_RCS_DONE" > /dev/ttyGS0` diagnostic appended at end

**Result:** Interactive shell on COM3 (ttyGS0) confirmed working. `echo OK; uname -a` → `OK`, `Linux NerveOS 6.11.0-sm8150`.

**Boot image:** `boot_nerveos_v12.img` permanently flashed to boot partition via `fastboot flash boot`.

**Known quirk:** Shell appears at t≈282s (needs a `\n` probe to wake). ~170s mystery delay in rcS before S01syslogd still unexplained but non-blocking.

**Reboot to fastboot:** Use `/sbin/reboot-bootloader` from the NerveOS shell — this uses `LINUX_REBOOT_CMD_RESTART2` syscall (NR=142 on aarch64) with "bootloader" argument, which the 6.11 kernel handles correctly. `busybox reboot bootloader` does NOT work (busybox ignores the argument). Writing `bootonce-bootloader` to misc partition (/dev/sda11) also does NOT work on this UEFI ABL. Script installed at `/mnt/rootfs/sbin/reboot-bootloader`.

### DRM/Display pipeline — session 6 (2026-04-21)

**Kernel config changes (v14→v17 series):**
- `CONFIG_DRM=y`, `CONFIG_DRM_MSM=y`, `CONFIG_DRM_MSM_DSI=y`, `CONFIG_DRM_MSM_DSI_7NM_PHY=y` — enabled DRM
- `CONFIG_DRM_PANEL_SAMSUNG_SOFEF00=y` — Samsung EA8076 (s6e3fc2x01) AMOLED panel for Mi 9
- `CONFIG_DRM_GEM_DMA_HELPER=y`, `CONFIG_DRM_GEM_SHMEM_HELPER=y` — must be `=y` not `=m` (syncconfig demotes them when new DRM options added — BUG: always verify after syncconfig)

**Panel driver fix (`panel-samsung-sofef00.c`):**
- Root cause: `sofef00_panel_prepare()` was sending DCS commands BEFORE DSI PHY PLL lock → EINVAL
- Fix: moved all DCS init into a new `sofef00_panel_enable()` callback; `prepare()` now only does regulator enable + GPIO reset
- Both `.prepare` and `.enable` added to `drm_panel_funcs` struct
- Source: `/opt/sm8150-mainline/drivers/gpu/drm/panel/panel-samsung-sofef00.c`

**Boot image format — critical lesson:**
- Mi 9 ABL ONLY correctly handles v1 (header_version=0) boot images
- v1 format: kernel blob = `Image.gz concatenated with DTB` (no separate `--dtb` section)
- Build: `cat Image.gz sm8150-xiaomi-cepheus.dtb > kernel_with_dtb.gz` then `mkbootimg --kernel kernel_with_dtb.gz ...` (no `--dtb` flag)
- Working v17 image: `/opt/boot_nerveos_v17.img` (10,297,344 bytes)

**Working state with v17:**
- `/dev/fb0` (msmdrmfb), `/dev/dri/card0`, `/dev/dri/renderD128` (Adreno 640 GPU) — all present
- Framebuffer: 1080×2340, 32bpp BGRA
- **NerveOS splash logo displayed** — hex mesh + NERVEOS title confirmed on physical screen
- Write() to `/dev/fb0` works via `busybox dd`. If write() fails ("not in virtual address space"), mmap() is required
- **Framebuffer pixel format: BGRX8888** (blue stored in byte 0, green byte 1, red byte 2) — swapping B and R gives yellow-green instead of teal. For teal RGB(0,215,195) write bytes [195, 215, 0, 255]
- **Framebuffer stride: 4320 bytes/line** (1080×4, no GPU padding). Pixel offset = `y * 4320 + x * 4`. Total FB size = 4320 × 2340 = 10,108,800 bytes. Using stride=4352 (assumed in session 6) causes diagonal line-wrap — each line shifts 8 pixels right, wrapping around after 135 lines.

**Framebuffer transfer technique (no python3 in initramfs):**
- Generate BGRA framebuffer image on Windows host with Python
- Gzip compress: 10MB → 49KB (99.5% compression ratio for structured image)
- Base64: 49KB → 65KB → split into 188 chunks of 350 chars each
- Send via serial: `busybox echo -n 'chunk' >> /tmp/lg64` (use `busybox echo`, NOT bare `echo` — busybox applets needed)
- Decode+write: `busybox base64 -d /tmp/lg64 | busybox gunzip | busybox dd of=/dev/fb0 bs=4096`
- Scripts: `C:\Windows\Temp\logo_gen.py` (generates image on Windows), `C:\Windows\Temp\send_logo_gz.py` (transfer+write)
- Total transfer: ~56 seconds, write: 60ms at 161MB/s

**Initramfs busybox environment (v17):**
- BusyBox v1.37.0 — applets available ONLY as `busybox <applet>` (not linked standalone)
- Available: base64, gzip/gunzip, wc, xxd, dd, echo, ls, cat
- NOT available: python3 (no python in initramfs), standalone `base64`, `wc`, `tr` etc.
- PATH: `/sbin:/usr/sbin:/bin:/usr/bin` — busybox is at `/bin/busybox`
- No /dev/sda* (UFS not visible in this initramfs; works in v12 sysvinit rootfs)
- No /sbin/reboot-bootloader (that's on sda31 rootfs, not in initramfs)

**v17 NOT permanently flashed** — device reboots to v12. To use v17:
`fastboot boot //wsl.localhost/Debian/opt/boot_nerveos_v17.img`

### Boot splash — session 7 (2026-04-21)

**Working boot image:** `boot_nerveos_v30.img` — permanently flashed to boot partition
- Init: `C:\Windows\Temp\nerveos-init-v18` (also at `initramfs/board/cepheus/init`)
- Logo: `initramfs/tools/logo_gen.py`, STRIDE=4320, SC=18, BGRX8888

**Boot splash sequence (init background job):**
1. Wait up to 20s for `/dev/fb0` to appear
2. Sleep 5s (let DRM settle)
3. Save FB sysfs to `/tmp/fb_diag.txt` for diagnostics
4. Decompress `/logo.gz` to `/tmp/logo.raw`
5. `dd if=/tmp/logo.raw of=/dev/fb0 bs=1048576` — direct write, no blank trick needed
6. Display updates immediately from the write (DRM scans fb0 directly)

**Key lessons:**
- Stride is 4320 (1080×4), NOT 4352. Session 6 assumption was wrong; kernel_v13 DRM doesn't pad.
- Write to /dev/fb0 immediately updates the display — no blank sysfs trigger needed.
- `echo 1 > blank` kills the display and `echo 0 > blank` does NOT reliably restore it from init.
- Decompress to temp file first (`> /tmp/logo.raw`), then `dd` — eliminates pipe timing issues.
- Do NOT redirect dd stderr to /dev/null during development — pipe to diag file instead.

### Session 9 fixes (2026-04-22)

**EFI=n — the root fix for Buildroot kernel UFS:**
- Root cause: Buildroot kernel had `CONFIG_EFI=y` + `CONFIG_EFI_STUB=y`. When ABL boots via UEFI, it provides its own DTB via EFI system table, ignoring our appended DTB. The ABL's EFI DTB has UFS disabled.
- Fix: `CONFIG_EFI=n`, `CONFIG_EFI_STUB=n` added to `kernel-nerveos-mainline.config`. With EFI disabled, ABL uses native ARM64 boot protocol (x3 register = our appended DTB). UFS nodes `&ufs_mem_hc`/`&ufs_mem_phy` in our DTS take effect.
- BATMAN_ADV: changed from `=m` to `=y` (built-in)
- Kernel rebuild running via screen session `nerveos-kernel` in WSL2 (started 2026-04-22 05:46)

**hived.conf duplicate key fix (`hived/cmd/hived/config.go`):**
- Bug: `ensureIdentity()` appended a new `[node]` section via `O_APPEND`, causing TOML parse error on second boot
- Fix: rewrites the entire config file via `toml.NewEncoder` + `os.WriteFile` — atomic replacement, no duplication

**Buildroot inittab fix (`target/etc/inittab`):**
- Bug: `sole::respawn:` — empty runlevels field (`::`). Real sysvinit IGNORES `respawn` entries with no runlevels.
- Fix: `MSM:2345:respawn:/sbin/getty -L ttyMSM0 115200 vt100` and `GS0:2345:respawn:/sbin/getty -L ttyGS0 115200 vt100`
- Also: `rcS:12345:wait:` → `rcS:2345:once:` (non-blocking, lets respawn entries activate)

**Buildroot linux-configure with spaces in path:**
- WSL PATH contains Windows paths with spaces, breaking `make` variable passing
- Fix 1: symlink `/opt/NerveOS-br2-ext` → `/mnt/c/Users/Forbidden User/HiveOS/br2-external`
- Fix 2: clean PATH to `/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin` before running make
- Invoke: `make -C /opt/NerveOS-project/buildroot BR2_EXTERNAL=/opt/NerveOS-br2-ext O=/opt/NerveOS/build/cepheus linux-configure`

**Kernel background build — screen session:**
- Background processes via `nohup`/`setsid`/`disown` all die when WSL session closes (SIGHUP propagates)
- Fix: `screen -dmS nerveos-kernel bash -c '...'` — screen survives WSL session closes
- Monitor: `screen -r nerveos-kernel` to attach, or `tail -f /opt/NerveOS/kernel-rebuild.log`

**Kconfig BIG_KEYS interactive prompt:**
- After EFI=n change, `make Image` triggers interactive syncconfig for `BIG_KEYS` (depends on `CRYPTO_LIB_CHACHA20POLY1305 = y`, which is `=m`)
- The dependency is a tristate comparison (`= y`) making BIG_KEYS invisible to `olddefconfig` but visible to interactive `syncconfig`
- Fix: run `yes "" | make ARCH=arm64 ... syncconfig` once to pre-handle all interactive prompts, then build

### Session 10 — Bluetooth working (2026-04-22)

**GENI UART DMA re-arm bug (root cause of all BT RX failures):**
- Symptom: After a successful BT init on first boot, subsequent cold boots failed with "Frame reassembly failed (-84)" and 0xfc00 tx timeout
- Root cause: `qcom_geni_serial_handle_rx_dma()` in `drivers/tty/serial/qcom_geni_serial.c` returns early when `SE_DMA_RX_LEN_IN = 0` (spurious DMA interrupt from chip startup noise) WITHOUT calling `geni_se_rx_dma_prep()` to re-arm the RX DMA. After this, UART RX is dead until port is closed/reopened.
- Fix (`tools/patch-geni-uart-dma.py`): Changed early `return` to fall through — re-arm DMA unconditionally, only skip `handle_rx_uart()` when `rx_in == 0`
- Kernel rebuilt (`tools/rebuild-kernel-geni.sh`) → `/tmp/Image_geni_fix.gz`
- This fix should be added as a numbered patch in `br2-external/board/cepheus/linux-patches/` (0007-fix-geni-uart-dma-rearm.patch) to persist across kernel rebuilds

**BT firmware symlinks (WCN3990 on SM8150 accepts WCN3990 on SDM845 firmware):**
- `/lib/firmware/qca/crbtfw01.tlv` → `crbtfw21.tlv` (crbtfw%02x = version 0x01 from version read)
- `/lib/firmware/qca/crnv01.bin` → `crnv21.bin`
- Firmware accepted: "QCA Patch Version:0x00006699", "QCA controller version 0x02241001"

**boot_geni_fix.img** — built by `tools/build-boot-geni.sh`:
- Kernel: `/tmp/Image_geni_fix.gz` (GENI DMA fix) + rebuilt DTB
- Ramdisk: extracted from v37 boot image (same Buildroot initramfs)
- Permanently flashed: `fastboot flash boot /opt/boot_geni_fix.img`
- hci0 init on every boot: `[    7.666349] Bluetooth: hci0: QCA setup on UART is completed`

**BT userspace blocked:** Device Python3 compiled without `socket.AF_BLUETOOTH`. No `hciconfig`/`bluetoothctl`/`hcitool` in current rootfs. hci0 exists but not up. Need BlueZ in Buildroot config.

**Tools added this session (all in `tools/`):**
- `patch-geni-uart-dma.py` — patches `qcom_geni_serial.c` DMA re-arm bug
- `rebuild-kernel-geni.sh` — rebuilds kernel after GENI patch
- `build-boot-geni.sh` — rebuilds DTB, concatenates kernel+DTB, builds boot image
- `patch-hci-qca-baudrate.py` — patches baudrate timeout to warn-only (no longer needed since firmware provides the vendor event, but kept for reference)
- `rebuild-hci-uart.sh` — rebuilds `hci_uart.ko` (original on device works fine; rebuild was a dead end)
- `hci-up.py` — HCI socket script (Python AF_BLUETOOTH not available on device; needs BlueZ)

### Bluetooth fully working — session 11 (2026-04-22)

**Problem summary from session 10:** hci0 registered and BT firmware downloaded OK, but hci0 was blocked with `HCI_UNCONFIGURED` flag because WCN3990 NVM (`crnv01.bin`) contained all-zero BD_ADDR. `HCIDEVUP` ioctl returned `EOPNOTSUPP`.

**Root cause:** Kernel sets `HCI_UNCONFIGURED` when `set_bdaddr()` is defined and `hdev->public_addr` = BDADDR_ANY after init.

**Fix:** Used BlueZ Management API (MGMT socket on `HCI_CHANNEL_CONTROL`) to send `MGMT_OP_SET_PUBLIC_ADDRESS (0x0039)` — the only command with `HCI_MGMT_UNCONFIGURED` flag. This calls `qca_set_bdaddr()` which sends `EDL_WRITE_BD_ADDR_OPCODE` vendor command to the chip. **The write persisted to WCN3990 NVM** — after reboot, chip loads the NVM with valid BD_ADDR and hci0 comes UP automatically. No management dance needed after the first successful write.

**Resulting BT state (auto-configured from NVM on every boot):**
- BD_ADDR: `00:17:F2:55:55:0D` (Qualcomm OUI + machine-id-derived bytes)
- BT version: 5.0 (version=0x09), Manufacturer: Qualcomm (0x001d)
- hci0 comes UP automatically via kernel's `power_on` workqueue (~6s after boot)
- `HCI_UNCONFIGURED` never set after NVM write

**bluetoothd setup:**
- Both `S30dbus` and `S40bluetoothd` were already in `/etc/init.d/` from Buildroot
- dbus was failing because `dbus` system user didn't exist: added `dbus:x:81:81:...:/run/dbus:/bin/false` to `/etc/passwd` and `/etc/group` (persistent on sda31 ext4)
- Created `/etc/bluetooth/main.conf` with `AutoEnable=true`
- bluetoothd 5.72 starts, enables SSP + LE, names device "BlueZ 5.72"
- Final `current_settings`: `POWERED SSP BREDR LE (0x00000ac1)`
- "Failed to set privacy: Rejected (0x0b)" — normal for WCN3990, LE privacy MAC rotation not supported; not a blocker

**Key kernel facts for session 12+:**
- Kernel 6.11 removed HCI sysfs attributes (`address`, `name`, `type`) — management socket is the only interface
- `hci-info.c` (`tools/hci-info.c`) uses `MGMT_OP_READ_INFO (0x0004)` to read controller state
- `mgmt_rp_read_info` field order: bdaddr, version, manufacturer, supported_settings, current_settings, dev_class, name, short_name (NOT what BlueZ docs from older versions show)
- BD_ADDR read via raw HCI socket times out when chip is in IBS sleep — use management socket instead

**Tools added (session 11):**
- `tools/hci-info.c` — MGMT READ_INFO client, reads BD_ADDR + settings from kernel cache
- `tools/hci-mgmt.c` — updated to use `HCIDEVUP` ioctl after `SET_PUBLIC_ADDRESS` (cleaner than async SET_POWERED); no longer needed on this device since NVM is programmed
- `/sbin/reboot-bootloader` installed on sda31

### Immediate next steps (session 9+)
- [x] Permanently flash boot splash image: `boot_nerveos_v30.img` flashed to boot partition (session 7)
- [x] Buildroot rootfs built successfully (session 8)
- [x] Added CONFIG_EFI=n to kernel config fragment (session 9)
- [x] Fixed hived.conf duplicate key bug in config.go (session 9)
- [x] Fixed inittab runlevels for real sysvinit (session 9)
- [x] Kernel rebuild running in screen session `nerveos-kernel` (session 9)
- [x] Kernel rebuild complete — `6.11.0-sm8150` with EFI=n, BATMAN_ADV=y, WireGuard=m
- [x] rootfs.ext4 rebuilt with fixed hived, inittab, and boot splash script
- [x] v37 boot image flashed + rootfs.ext4 flashed — permanently boots NerveOS Buildroot rootfs
- [x] UFS working — 31 partitions visible on `/dev/sda`
- [x] WireGuard working — `modprobe wireguard` → `hive0` UP at `10.42.x.x/16`
- [x] hived running — PID ~337, stable node ID persists across reboots, correct single `[node]` section
- [x] Boot splash: `S05splash` init script writes logo.gz to `/dev/fb0`; fbcon detach timing needs work (flashes briefly) — acceptable for now
- [x] **Bluetooth fully working** — WCN3990 BT initialized, firmware downloaded, hci0 registered (session 10)
- [x] **boot_geni_fix.img** permanently flashed — GENI UART DMA re-arm fix + BT-capable kernel (session 10)
- [x] **hci0 fully UP with LE** — BD_ADDR `00:17:F2:55:55:0D` persisted to WCN3990 NVM (session 11)
- [x] **bluetoothd 5.72 running** — dbus user added, S30dbus+S40bluetoothd already in rootfs init.d (session 11)
- [x] **reboot-bootloader installed** — `/sbin/reboot-bootloader` on sda31 rootfs (session 11); now also in `rootfs-overlay/sbin/` (session 17)
- [x] **DRM display pipeline working** — MDSS → DPU → DSI → sofef00 panel (session 17); boot image `boot_compositor_v2.img` permanently flashed
- [x] **nerveos-shell Wayland compositor running** — PID auto-started by S80nerveos-shell; `wayland-0` socket up; DSI-1 1080×2340 @ 60Hz; pixman renderer (session 17)
- [x] **ST FTS touchscreen working** — event3 "fts" at i2c-0/0-0049, FW VER=0x0045; touch_down_cb in compositor; Start menu opens on tap (session 18)
- [x] **USB serial stable** — S25usbnet removed; initramfs g0 gadget persists through switch_root; COM3 auto-login on every boot (session 18)
- [x] **Switched to PostmarketOS base** — dropped Buildroot approach; pmOS + phosh on Mi 9 (session 19)
- [x] **USB networking persistent** — `usb-moded` was reconfiguring gadget; masked it; NCM at 172.16.42.1 stable (session 19)
- [x] **phosh GUI fully working** — pixman renderer (`WLR_RENDERER=pixman` via `~/.phoshdebug`); greetd → phosh-session direct (session 19)
- [ ] Add hived daemon to pmOS as an Alpine package
- [ ] Set up WireGuard mesh on pmOS (hive0 interface)
- [ ] Deploy NerveOS branding (os-release, motd) to pmOS pmaports
- [ ] Test inter-node WireGuard peering (two nodes, static peer config)

### AI Inference — session 24 (2026-05-04)

**Qwen2.5-1.5B-Instruct running on-device at 6.8 tok/s:**

- **Binary**: `llama-cli` + `llama-server` cross-compiled with musl aarch64 toolchain (musl.cc GCC 11.2.1) — works on Alpine/pmOS musl libc
- **Model**: `/home/user/models/Qwen2.5-1.5B-Instruct-Q4_K_M.gguf` (940MB, 4-bit quantized)
- **Service**: `nerveos-ai.service` (systemd) — `llama-server --host 127.0.0.1 --port 8080 --ctx-size 4096 --threads 4 --chat-template chatml`
- **CLI**: `/usr/local/bin/nerveos-ai` — queries AI with live system context (free RAM, load, battery, disk)
- **API**: OpenAI-compatible at `http://127.0.0.1:8080/v1/chat/completions`
- **Speed**: ~22 t/s prompt ingestion, ~6.8 t/s generation (A76 CPU, 4 threads)
- **Internet setup**: SSH reverse tunnel from device to WSL tinyproxy (port 9999→8888); `AllowTcpForwarding yes` in sshd_config

**Build chain (in WSL for device):**
```bash
# Toolchain: /opt/aarch64-linux-musl-cross/bin/
# Source: /opt/llama.cpp/ (build-musl dir)
# cmake -DCMAKE_C_COMPILER=aarch64-linux-musl-gcc -DGGML_NATIVE=OFF -DBUILD_SHARED_LIBS=OFF
```

**Next steps for AI:**
- Wire to `hived/internal/brain/` plugin system — LLM as resource scheduling decision maker
- Add device telemetry streaming (continuous context updates)
- Evaluate Vulkan backend for Adreno 640 acceleration (potential 5-10x speedup)
- Consider quantized embedding model for semantic resource matching

---

### Audio Investigation — sessions 24+ (2026-05-04)

**DPCM/WCD9340 audio path fully debugged:**

**What works:**
- DPCM routing: `SLIMBUS_0_RX Audio Mixer MultiMedia1` (numid=236=1) connects MultiMedia1 FE to SLIM Playback BE
- WCD9340 hw_params: `ch_count=2, port_mask=0x30000` (SLIMbus ports 16+17 = RX0+RX1) — confirmed by debug module
- EAR PA: `WCD934X_ANA_EAR (0x060a)` toggles 0x40→0xC0 on playback (bit7=EAR PA enable) — DAC event fires correctly
- LINEOUT1/2 PA: `WCD934X_ANA_LO_1_2 (0x060b)` toggles 0x3C→0xFC on playback — audio reaches LINEOUT1/2 pins
- RX_BIAS supply: enabled (0x0608=0xC1 during playback)
- ALSA state saved at `/var/lib/alsa/asound.state` with full routing (EAR + HPH + LINEOUT + SPKR paths)
- ExecStartPre=`alsactl restore 0` in PA override ensures routing before PA opens PCM

**Mi 9 speaker hardware (cepheus-oss DTS):**
- Speaker amps on `qupv3_se4_i2c` = `i2c@a84000` (GPIO 51/52, now enabled as i2c-0)
- **TAS2557** (TI) at I2C 0x4c — main speaker amp, I2S digital input, IRQ=GPIO 60
- **CS35L41** (Cirrus) at I2C 0x40, I2S digital input, reset=GPIO 89, IRQ=GPIO 10
- DAPM route `"hifi amp", "LINEOUT1"` is VIRTUAL (machine driver) — actual audio via **Quaternary MI2S** → CS35L41/TAS2557
- LINEOUT1/2 do NOT go to speaker amps as analog (both amps are digital I2S-only)

**CONFIRMED WORKING (session 24 testing):**
- `speaker-test -D hw:0,0 -t sine -f 440` plays audibly from BOTH earpiece AND main speaker
- CS35L41 operates in analog passthrough from LINEOUT1/2 without I2C initialization
- Audio settings app (pmOS/phosh) only shows earpiece path — no UCM profile for speaker yet
- Raw ALSA (hw:0,0) works; PulseAudio stereo-fallback profile only uses HPH/EAR path

**What's NOT working:**
- PulseAudio doesn't know about speaker path (needs UCM profile mapping PA sink to LINEOUT routing)
- Audio settings/media apps play over earpiece only (PA selects stereo-fallback → HPH)

**Next steps for speaker audio:**
1. Add `&quat_mi2s` backend DAI link to sm8150-xiaomi-cepheus.dts sound card
2. Add CS35L41 DTS node at i2c9@0x40 with reset=GPIO89, IRQ=GPIO10
3. Check `CONFIG_SND_SOC_CS35L41_I2C` in kernel config and build driver
4. Add "hifi amp" DAPM widget to sm8150.c machine driver, route QUAT MI2S → CS35L41

**Sleep prevention (on-device):**
- `sleep.target`, `suspend.target` etc. all masked
- `/etc/systemd/logind.conf.d/no-sleep.conf`: IdleAction=ignore, all handle-* = ignore
- `no-sleep-inhibit.service`: `systemd-inhibit sleep infinity` (auto-restart)
- gsettings: idle-delay=0, screensaver lock disabled, power-button=nothing
- **Reboot workaround**: `systemctl stop no-sleep-inhibit.service && sudo reboot`

**Current flashed boot image:** `/opt/boot_spkramp.img` — has i2c9 bus (GPIO51/52), qupv3_id_1+gpi_dma1 enabled

**Debug modules on device:**
- `/lib/modules/6.11.../kernel/snd-soc-wcd934x.ko` (378368B): `WCD934X_EAR_DAC_EVENT`, `WCD934X_HW_PARAMS` debug prints
- `/lib/modules/6.11.../kernel/snd-soc-sm8150.ko`: `SM8150_SLIM_HW_PARAMS`, `SM8150_FIXUP`, `SM8150_CODEC_DAI` debug prints

---

### pmOS Session 19 (2026-04-26) — PostmarketOS base, phosh GUI working

**Direction pivot:** Dropped Buildroot rootfs + custom compositor. Now running PostmarketOS (pmOS) with phosh on Mi 9. hived + WireGuard mesh run on top of pmOS.

**Working setup:**
- Boot: NerveOS 6.11 kernel (`boot_v10.img`, EFI=n, UFS fix, sofef00 fix) + pmOS phosh initramfs
- Rootfs: pmOS phosh image (`pmOS-cepheus-rootfs-v4.img`) flashed to Android `userdata` partition
- SSH: `ssh -i ~/.ssh/root.pem user@172.16.42.1` (key at `/home/user/.ssh/root.pem` in WSL)
- Phosh: running directly via `greetd → phosh-session` (no phrog greeter, no lock screen)

**Key fixes for pmOS:**
- `usb-moded.service` → masked (was reconfiguring USB gadget, causing disconnect)
- `WLR_RENDERER=pixman`, `LIBGL_ALWAYS_SOFTWARE=1`, `GSK_RENDERER=cairo` in `~/.phoshdebug` (sourced by phosh-session) — NerveOS 6.11 kernel GPU ioctl doesn't match pmOS Mesa 6.17 ABI
- `/etc/phrog/greetd-config.toml` → `command = "phosh-session"`, `user = "user"` (bypasses phrog, avoids dual-phoc DRM conflict)
- `/etc/NetworkManager/conf.d/usb0-unmanaged.conf` → NM ignores usb0
- `systemd.mask=systemd-time-wait-sync.service` in kernel cmdline (prevents NTP blocking boot)

**Rootfs image structure:** GPT disk with 4096-byte sectors, flashed to Android `userdata`
- Partition 2 at offset 511,705,088 bytes: ext4, label `pmOS_root`, UUID `a539a88e-05cd-4980-98c3-b28214596d15`
- Offline patching: `dd skip=124928 count=609531 bs=4096` to extract, mount, patch, `dd seek=124928 conv=notrunc` to write back

**Current flashed images:**
- Boot: `C:\Windows\Temp\boot_v10.img`
- Rootfs: `C:\Windows\Temp\pmOS-cepheus-rootfs-v4.img`

### Rootfs build plan
The Buildroot config (`NerveOS_cepheus_defconfig`) is ready. Build produces:
- `rootfs.ext4` — flash to `/dev/sda31` via `fastboot flash userdata`
- `Image` + `qcom/sm8150-xiaomi-cepheus.dtb` — use pre-built `kernel_v13.gz` for boot image (don't rebuild kernel via Buildroot unless needed)

**To run the build in WSL2:**
```bash
wsl -d Debian -u root -- bash /mnt/c/Users/Forbidden\ User/HiveOS/nerveos-build.sh
# Monitor: wsl -d Debian -u root -- tail -f /opt/NerveOS/build/cepheus/build.log
```

**sda31 partition:** On Mi 9, `/dev/sda31` = `userdata` partition (128GB - system). This is where the NerveOS rootfs lives. Flash with:
```bash
fastboot flash userdata /opt/NerveOS/build/cepheus/images/rootfs.ext4
```

**Known issue:** Buildroot will try to build the kernel from source (sm8150-mainline git). This takes a long time. If using the pre-built `kernel_v13.gz`, the kernel build can be skipped with `BR2_LINUX_KERNEL=n` override, but this requires a separate defconfig or override file.

### WiFi Investigation — session 12 (2026-04-23)

**Goal:** Get WCN3990/ath10k WiFi working on Mi 9 (SM8150).

**Architecture clarified:**
- SM8150 WCN3990 WiFi uses ath10k_snoc driver (mainline)
- WCN3990's Q6 WLAN processor must register WLFW QMI service (ID 0x45) on QRTR
- ath10k_snoc registers a QRTR lookup for WLFW and waits indefinitely
- WCN3990 communicates via QRTR over modem GLink SMEM transport (SPI 449, mailbox 12)
- The modem's WLAN protection domain (`msm/modem/wlan_pd`) handles WCN3990 boot and WLFW registration

**Investigation findings:**
1. All 4 WCN3990 regulators ARE on (pm8150_l1a_0p75, pm8150_l7a_1p8, pm8150l_l2c_1p3, pm8150l_l11c_3p3)
2. WCN3990 has NO boot ROM — needs firmware loaded by modem's internal PIL before WLFW can register
3. TZ blocks AP (Linux kernel) from loading WCSS firmware — PAS ID 6 returns EINVAL from `qcom_mdt_load()`
4. The modem (remoteproc0) was crashing every ~40s with "fatal error without message"
5. No QRTR services from modem visible during 40s window (modem crashes before QRTR stack initializes)
6. **ROOT CAUSE**: Modem firmware requires the AP's IPA (IP Accelerator) QMI service to be available

**IPA breakthrough (key finding — later revised):**
- `CONFIG_QCOM_IPA=m` is compiled as module but NOT auto-loaded (no SM8150 IPA DTS node)
- Session 12 claimed `modprobe ipa` stopped 40s crash — REVISED in session 13: this was a FALSE NEGATIVE due to 12s polling interval (modem crashed every 40s but polls at 12s intervals missed the crash, always seeing "running" at re-checked state)
- The `modprobe ipa` approach does NOT prevent the crash

**QRTR routing investigation (session 13 — 2026-04-23):**
- Modem's QRTR packets ARE received by the AP (`qcom_smd_qrtr` accepts len=52 v0=01 packets)
- But the AP QRTR nameserver does NOT forward service lookups to the modem (AP→modem QRTR routing broken)
- Userspace IPA stub (service 0x31) registered on QRTR but modem never connects to it
- IPA stub only receives QRTR control messages from AP nameserver (node 1:0xFFFFFFFE), never from modem
- Root cause confirmed: QRTR inter-node service discovery (AP→modem NEW_SERVER forwarding) is broken in mainline 6.11 kernel on SM8150

**QRTR HELLO bug (session 13):**
- After modem crash+restart, first packet (len=52 v0=01) is rejected: "invalid ipcrouter packet"
- Root cause: `qrtr_endpoint_post()` had `if (!size || len != ALIGN(size, 4) + hdrlen)` — the `!size` condition rejects HELLO with 0-byte size field
- Android kernel has `if (len != ALIGN(size, 4) + hdrlen)` (no `!size` check)
- Patch applied: removed `!size ||` from `af_qrtr.c` in Buildroot kernel at `/opt/NerveOS/build/cepheus/build/linux-4a8d88483/net/qrtr/af_qrtr.c`
- Patched `qrtr.ko` installed to rootfs at `/lib/modules/6.11.0-sm8150/kernel/net/qrtr/qrtr.ko` (39448B vs original 38784B)
- BUT: the HELLO fix is SECONDARY — the 40s crash happens before any restart HELLO
- NOTE: modem's initial HELLO (before first crash) has size=20 (correct) → passes both old and new code
- Modem's post-crash HELLO has size=0 → rejected by old code, my fix also rejects it because: `len=52 ≠ ALIGN(0,4) + 32`
- **CORRECT fix**: detect len=52 and size=0 case (52-32=20 bytes present but size field says 0), set size=20 before check

**Debug modules installed (session 13):**
- `qrtr-smd.ko` with debug: prints `qrtr_rx len=X v0=YY` for every received packet
- Installed to `/lib/modules/6.11.0-sm8150/kernel/net/qrtr/qrtr-smd.ko` (7688B vs 7144B original)
- `/etc/init.d/S49ipa_stub` installed: starts `ipa_stub_c` in background, then starts modem after 3s
- `/usr/bin/ipa_stub_c` installed: static C binary (711KB, fixed sockaddr_qrtr layout)

**Current device state (session 13 end):**
- Device is rebooted with patched QRTR + debug SMD + S49ipa_stub autostart
- IPA stub starts at boot but QRTR `sendto()` to register service returns ENOSPC after modem crash cycles
- Modem still crashes every 40s — IPA service unreachable via QRTR
- /dev/shm fills with IPA stub log (QRTR ctrl message flood) — redirect output to /dev/null needed

**What we've confirmed:**
- wlanmdsp.mbn (WCN3990 Q6 firmware, 4.05MB ELF) is in `/lib/firmware/qcom/sm8150/` (copied from /dev/sde52)
- All 496 modem firmware partition files copied to `/lib/firmware/qcom/sm8150/`
- qcom_pd_mapper IS working: registers SERVREG service (0x40) on QRTR
- SM8150's qcom_pd_mapper config includes `mpss_wlan_pd` with `"wlan/fw"` service
- Android sm8150.dtsi uses `compatible = "qcom,ipa"` for IPA node (NOT `qcom,sm8150-ipa`)
- SM8150 IPA: IPAv4.1 (hw_ver=15), base=0x1e00000 (0x34000), GSI=0x1e04000 (0x28000), IRQ SPI 311+432

**CORRECT next steps for WiFi (session 14+):**
1. **Make IPA kernel driver probe on SM8150**: Add `"qcom,ipa"` to `ipa_main.c` compatible list using IPA_VERSION_4_1 config (mainline has `IPA_VERSION_4_1` enum but no data struct yet). Use `ipa_data_v4_2` (sc7180) as starting point. Update DTS node compatible string.
2. Alternatively: debug WHY ap→modem QRTR NEW_SERVER forwarding is broken. Check `qrtr_ns_worker()` in ns.c and `qcom_smd_qrtr_send()`.
3. **Fix QRTR HELLO post-crash**: Change check to `if (size == 0 && len > hdrlen) size = len - hdrlen; if (len != ALIGN(size, 4) + hdrlen)` — allows modem's post-crash HELLO (len=52, size=0, actual payload=20B)
4. Fix IPA stub log flooding: redirect to `/dev/null` in S49ipa_stub, or only log non-ctrl messages

### WiFi Investigation — session 14 (2026-04-23)

**QRTR HELLO fix — complete (session 14):**
- Session 13 applied partial fix (remove `!size ||`). This was INCOMPLETE — modem post-crash HELLO still rejected
- Session 14: Added full fix in `af_qrtr.c`:
  ```c
  if (size == 0 && len > hdrlen) size = len - hdrlen;
  if (len != ALIGN(size, 4) + hdrlen) goto err;
  ```
- RESULT from check_qrtr_fix.py: Initial boot HELLOs (t=9s) all ACCEPTED ✓. But post-crash HELLO (t=50s) STILL rejected ("invalid ipcrouter packet").
- `handling crash #4` at t=172s means modem is still crashing every ~40-45s
- 90s monitor shows 0 NEW crashes during window (crashes happen fast, modem recovers quickly)

**Why post-crash HELLO still fails despite complete fix:**
- The initial HELLOs at t=9s pass → `size != 0` in initial HELLO (modem sets it correctly initially)
- The post-crash HELLO at t=50s fails → BUT the fix handles size=0! So either:
  a) The post-crash HELLO has a different size value that makes ALIGN check fail for other reasons
  b) The failure is at a DIFFERENT check: type check, port lookup, or socket queue full
- Added rejection reason labels to each `goto err` in `qrtr_endpoint_post()`:
  `REJECT_ALIGN`, `REJECT_CTRL_SIZE`, `REJECT_TYPE`, `REJECT_NO_PORT`, `REJECT_QUEUE_FULL`
- Also added `pr_debug()` print showing len/size/hdrlen/type/dst_port before each check
- New debug qrtr.ko built (13082B gz) at `C:\Windows\Temp\qrtr_debug_reject.ko.gz`

**Module hot-swap issue (session 14):**
- rmmod qrtr-smd + modprobe new qrtr-smd → SEGFAULT (Segmentation fault on modprobe)
- Root cause: modem GLink channel closes when qrtr-smd rmmod'd; new module can't safely reattach to half-initialized rpmsg channel
- Fix: must install modules to disk and REBOOT (not hot-swap)
- Always reboot to load new modules — do NOT rmmod/modprobe in session

**Current on-device state (as of session 14):**
- `/lib/modules/6.11.0-sm8150/kernel/net/qrtr/qrtr.ko` — complete HELLO fix + rejection reason labels (NOT YET INSTALLED — COM3 stalled when install_and_monitor.py ran)
- `/lib/modules/6.11.0-sm8150/kernel/net/qrtr/qrtr-smd.ko` — original (restored from .bak after segfault)
- `/usr/bin/ipa_stub_c` — static C IPA stub
- `/etc/init.d/S49ipa_stub` — redirects to /dev/null (fixed session 14)
- Device needs power cycle to clear USB serial stall, then debug qrtr.ko install

**Next steps:**
1. Power cycle device → run install_and_monitor.py (installs debug qrtr.ko with rejection labels, reboots, monitors)
2. Check dmesg for `REJECT_*` labels to find exactly which check fails for post-crash HELLO
3. Based on finding: either fix that check OR investigate why the modem crashes at all (IPA service not found)
4. If failure is `REJECT_QUEUE_FULL`: NS socket receive buffer is full after crash storm — need to drain it or increase buffer size
5. If failure is `REJECT_TYPE`: post-crash HELLO goes to wrong dst_port
6. If IPA kernel driver route needed: add `"qcom,sm8150-ipa"` compatible + ipa_data_v4_1 data + GSI regs (see analysis in session 14)

**Key discovery — why QRTR IPA kernel driver approach is complex:**
- IPA_VERSION_4_1 not in `ipa_reg.c` switch → returns NULL → probe fails immediately
- IPA_VERSION_4_1 not in `gsi_reg.c` switch → same issue
- Would need: new `ipa_reg-v4.1.c`, new `ipa_data-v4.1.c`, DTS node in sm8150.dtsi or cepheus.dts
- SDM845 IPA DTS is reference: same IRQs (SPI 311 + SPI 432), same GSI base (0x1e04000), IPA base 0x1e40000
- BUT SM8150 IPA (hwver=4.1) register layout may differ from v3.5.1 (SDM845) — need to research
- Alternative: try `IPA_VERSION_3_5_1` with SM8150 DTS (same hardware? risky)

**Interconnect/NoC path needed for IPA DTS:**
- SDM845 uses: `aggre2_noc MASTER_IPA → mem_noc SLAVE_EBI1`, `aggre2_noc → system_noc SLAVE_IMEM`, `gladiator_noc → config_noc SLAVE_IPA_CFG`
- SM8150 interconnect names may differ — need to check sm8150.dtsi and icc driver

**Tools created (sessions 12+13+14):**
- `/opt/wcss_boot/wcss_boot.c` — WCSS PIL loader (blocked by TZ, not usable but kept for reference)
- `C:\Windows\Temp\ipa_*.py` — Various IPA stub test scripts
- `C:\Windows\Temp\install_and_monitor.py` — Main install+test script (close/reopen COM3 pattern)
- `C:\Windows\Temp\qrtr_debug_reject.ko.gz` — Debug qrtr.ko with rejection reason labels
- Buildroot kernel patches in `/opt/NerveOS/build/cepheus/build/linux-4a8d88483/net/qrtr/`

### WiFi Investigation — sessions 15+16 (2026-04-23 to 2026-04-24)

**IPA driver fully working (session 15):**
- Created `ipa_data-v4.1.c` based on v4.2 with SM8150-specific endpoint assignments (tx_base=0..9, rx=10..22, FLAVOR_0=0x0a0d0a17)
- Set `.version = IPA_VERSION_4_2` in data to disable hash table size validation (SM8150 hashed tables have size=0)
- Added `ipa_reg-v4.1.c` mapping and `gsi_reg-v4.1.c` mapping to existing v4.2/v4.0 layouts
- Added DTS node `compatible = "qcom,sm8150-ipa"` with correct register regions, IRQs, SMP2P, IOMMU
- IPA probe now succeeds: all init steps return 0, "IPA driver initialized" at t≈6.4s

**IPA QMI service registered:**
- svc=0x31 inst=0x101 registers on QRTR → modem is notified ✓
- `ipa_smp2p_notify_ap()` added: forces clock-enabled=1 and valid=1 at BEFORE_POWERUP (bypasses pm_runtime_get_if_active which returns 0 when IPA is in runtime suspend)
- Power_on=false to avoid PM underflow on subsequent crash cycles

**QRTR: modem queries pd_mapper for tms services:**
- Modem sends `GET_DOMAIN_LIST_REQ` for `tms/pdr_enabled` and `tms/pddump_disabled` (NOT "wlan/fw")
- Added SM8150-specific `mpss_wlan_pd_sm8150` to pd_mapper with both TMS services + PDR + pddump_disabled
- pd_mapper confirms these domains → modem gets the info ✓

**Modem still crashes every 40s — root cause confirmed (session 16):**
- Confirmed via `/proc/interrupts`: `ipa-clock-query` and `ipa-setup-ready` SMP2P have ZERO fires — modem's IPA driver never runs
- The 40s crash is the modem's wlan_pd initialization timeout (NOT cellular network reset)
- The modem queries tms services from pd_mapper then does nothing for 40s → crashes
- Crash is at modem CORE level (entire modem resets, not just wlan_pd), even though PDR info is provided

**Module auto-load fix:**
- Added `/etc/init.d/S11modprobe` to Buildroot rootfs: loads `qrtr_smd`, `qcom_pd_mapper`, `ipa` + starts modem
- Modules weren't auto-loading because modules.dep was inconsistent after manual ko replacements

**WCN3990 oscillator clock fixed:**
- Found: `sm8150.dtsi` wifi node has `clocks = <&rpmhcc RPMH_RF_CLK2>, <&aoss_qmp>` but our `&wifi` override was missing these
- Added clocks to `sm8150-xiaomi-cepheus.dts` wifi node
- Confirmed: `rf_clk2 enable_count=1` at 38.4MHz — clock IS enabled at ath10k_snoc probe time
- BUT: modem still crashes every 40s despite clock being on

**Current state (end of session 16):**
- All infrastructure in place: IPA probe, QRTR routing, SMP2P, pd_mapper, module autoload, RF clock
- WCN3990 still does NOT boot — the modem's wlan_pd fails every 40s
- Hypothesis: modem's wlan_pd needs to load `wlanmdsp.mbn` firmware via **QMI Remote File System (RFS)** from the Linux file system, and we have no RFS server
- Evidence for RFS hypothesis: no WLFW (svc=0x45) ever registers; modem has ample time but can't proceed; no kernel-visible error

**On-device state (session 16 end):**
- Permanently flashed boot image: `boot_geni_fix.img` (GENI DMA fix kernel)
- `/etc/init.d/S11modprobe` added to rootfs (auto-loads qrtr_smd, pd_mapper, ipa; starts modem)
- `/etc/init.d/S49ipa_stub` disabled (was conflicting with kernel IPA QMI)
- `/lib/modules/6.11.0-sm8150/kernel/drivers/net/ipa/ipa.ko` — latest version with all fixes
- `/lib/modules/6.11.0-sm8150/kernel/drivers/soc/qcom/qcom_pd_mapper.ko` — SM8150 PDR+pddump version
- `sm8150-xiaomi-cepheus.dts` patched with WiFi clocks (RPMH_RF_CLK2 + aoss_qmp)
- `boot_wifi_clk.img` at `/opt/boot_wifi_clk.img` — test image with new DTB (NOT permanently flashed)

**Next steps for WiFi:**
1. **Implement minimal RFS server**: Serve `wlanmdsp.mbn` to modem via QMI RFS over QRTR/RPMSG. The modem's wlan_pd likely requests firmware this way. The RFS channel name is probably "MPSS_ESMSKA" or similar GLink channel.
2. **Alternative**: Check if modem can access wlanmdsp from its own UFS path (/dev/sde partition layout)
3. **Debug RFS traffic**: Monitor GLink channels for file-access pattern (file read requests to Linux FS)
4. **SMMU for WCSS**: If RFS isn't the issue, the WCSS SMMU configuration (SIDs 0x1820/0x1821) might need adding to apps_smmu, preventing modem PIL from loading firmware into WCN3990 address space

**Key files modified in kernel source (need patches):**
- `drivers/net/ipa/ipa_main.c` — SM8150 compatible, probe tracing, BEFORE_POWERUP qmi_setup
- `drivers/net/ipa/ipa_modem.c` — BEFORE_POWERUP: smp2p_notify_ap + ipa_qmi_setup
- `drivers/net/ipa/ipa_qmi.c` — idempotency guard in ipa_qmi_setup
- `drivers/net/ipa/ipa_smp2p.c` — ipa_smp2p_notify_ap() forcing clock=ON with power_on=false
- `drivers/net/ipa/ipa_smp2p.h` — declaration for ipa_smp2p_notify_ap
- `drivers/net/ipa/data/ipa_data-v4.1.c` — SM8150 IPA data (new file)
- `drivers/net/ipa/ipa_data.h` — ipa_data_v4_1 extern
- `drivers/net/ipa/ipa_reg.c` — IPA_VERSION_4_1 → ipa_regs_v4_2
- `drivers/net/ipa/gsi_reg.c` — IPA_VERSION_4_1 → gsi_regs_v4_0
- `drivers/net/ipa/Makefile` — added 4.1 to IPA_DATA_VERSIONS
- `drivers/soc/qcom/qcom_pd_mapper.c` — SM8150 PDR-enabled wlan_pd entry
- `arch/arm64/boot/dts/qcom/sm8150.dtsi` — IPA node at 0x1e40000 with smp2p, iommu, etc.
- `arch/arm64/boot/dts/qcom/sm8150-xiaomi-cepheus.dts` — WiFi clock fix (RPMH_RF_CLK2)
- `net/qrtr/af_qrtr.c` — HELLO fix (size=0 post-crash handling)

### nerveos-shell Wayland compositor (session 17 — 2026-04-24)

**All source files complete:**
- `nerveos-shell/src/nerveos.h` — structs, constants, all prototypes
- `nerveos-shell/src/main.c` — wlroots init, event loop, 1s tick timer via `wl_event_loop_add_timer`
- `nerveos-shell/src/output.c` — DRM output management, `output_is_internal()` (DSI prefix), mode switching on hotplug
- `nerveos-shell/src/view.c` — XDG shell windows, WinCE decorations (phone) / flat borders (desktop), tiling, drag-move, close button, title
- `nerveos-shell/src/input.c` — keyboard (xkb, Alt+F4, Ctrl+Alt+Backspace), pointer (motion/button/scroll), touch, seat caps, close-btn hit test
- `nerveos-shell/src/shell.c` — Cairo+Pango text rendering via `wlr_buffer_impl` wrapping cairo pixels, taskbar draw, clock tick
- `nerveos-shell/meson.build` — meson build, deps: wlroots-0.18, wayland-server, xkbcommon, libinput, cairo, pangocairo, libdrm

**Key implementation notes:**
- Text rendering: `shell_pixel_buffer` wraps `cairo_surface_t` as a `wlr_buffer` (implements `begin_data_ptr_access` with `DRM_FORMAT_ARGB8888`); attached to `wlr_scene_buffer` — compatible with wlroots 0.18 API
- Phone mode: WinCE palette (#d4d0c8 taskbar, #0000a8 title bars, #418f2d Start button), 40px taskbar at bottom, all windows auto-tile to fill usable area
- Desktop mode: dark gray functional UI (CLR_DT_* palette), 32px taskbar, windows draggable by titlebar, desktop detected by DSI output name heuristic
- Mode switches automatically when external DRM output connects/disconnects
- Buildroot package: `br2-external/package/nerveos-shell/` (meson-package, site=`$(BR2_EXTERNAL_NERVEOS_PATH)/../nerveos-shell`)

### brain resource manager (session 17 — 2026-04-24)

**All source files complete in `hived/internal/brain/`:**
- `action.go` — platform-agnostic `Action` interface
- `brain.go` — Manager, Plugin interface (`Tick(SystemState) []Action`), 1s loop, UNIX socket at `/var/run/brain.sock`
- `monitor.go` (linux) — `/proc/stat` CPU, `/proc/meminfo` RAM, per-proc `/proc/PID/stat`, `/sys/class/power_supply` battery
- `actuator.go` (linux) — `NiceAction` (syscall.Setpriority), `OOMAction` (/proc/PID/oom_score_adj), `SwappinessAction`
- `policy.go` — 4 plugins: ResourceGuard (hived at -10/-900), IdleThrottler (hogs > 75% CPU get nice=+10), MemoryPressure (RAM>80% → OOM+swap), PowerSaver (battery<15% → nice=+15 for non-critical)
- `socket.go` — commands: `ping`, `status` (JSON), `procs` (top 20 by CPU)
- `hived/cmd/hived/priority_linux.go` — `init()` sets nice=-10 + oom_score_adj=-900 before main()

**hived launch:** `br2-external/package/hived/hived.init` uses `-N -10` with start-stop-daemon

### Display / Compositor — session 17 (2026-04-24)

**Root cause of blank screen (all previous sessions):** `fixpanel.py` truncated `/opt/sm8150-mainline/drivers/gpu/drm/panel/panel-samsung-sofef00.c` to 138 lines. The file was missing `probe()`, `of_match_table`, and `module_mipi_dsi_driver()` registration. The driver object compiled successfully but was never registered on the MIPI DSI bus (`/sys/bus/mipi-dsi/drivers/` empty). Panel never probed → DSI component never added → DRM never initialized → no card0.

**Fix:** Copied complete Buildroot kernel sofef00.c (333 lines, already has the `enable()` fix) to sm8150-mainline. Rebuilt sm8150-mainline kernel.

**Root cause 2 (compositor startup failure):** `LIBSEAT_BACKEND=direct` is not a valid libseat backend name. Libseat supports: `logind`, `seatd`, `noop`. Fix: changed to `LIBSEAT_BACKEND=noop` in `S80nerveos-shell` init script and overlay.

**DRM pipeline confirmed working:**
- `dispcc` (af00000) probing ✓ (driver symlink present; was named differently than checked)
- `msm-mdss ae00000` → `msm_dpu ae01000` → `msm_dsi ae94000` → `panel-oneplus6` (sofef00) ✓
- connector: DSI-1, 1080×2340 @ 60Hz, physical size 68×145mm
- `card0`, `renderD128`, `fb0` all present after fix

**nerveos-shell startup sequence confirmed:**
- libseat backend `noop` — seat opened immediately ✓
- wlroots DRM backend on `/dev/dri/card0` (msm) ✓
- Atomic DRM interface + ADDFB2 modifiers ✓
- 8 DRM planes, 1 CRTC ✓
- Pixman renderer + DRM dumb allocator (1080×2340 buffers) ✓
- libinput: gpio_keys, pm8941_pwrkey, pm8941_resin ✓
- `WAYLAND_DISPLAY=wayland-0 mode=phone` ✓ — phone UI active

**Current boot image:** `boot_compositor_v2.img` at `/opt/boot_compositor_v2.img`
- Kernel: sm8150-mainline with fixed sofef00.c, EFI=n, DRM=y, panelSOFEF00=y
- DTB: Buildroot DTS with dispcc, mdss, dsi0, panel@0 (samsung,s6e3fc2x01), pinctrl, UFS voltage fix
- Ramdisk: extracted from boot_compositor.img (Buildroot initramfs)
- Cmdline: `clk_ignore_unused pd_ignore_unused console=tty0 ...` (NO nomodeset)

**Rootfs overlay additions (session 17):**
- `rootfs-overlay/sbin/reboot-bootloader` — 416-byte ARM64 ASM binary (LINUX_REBOOT_CMD_RESTART2 "bootloader")
- `rootfs-overlay/etc/init.d/S80nerveos-shell` — fixed: `LIBSEAT_BACKEND=noop`

**Key sm8150-mainline files modified (session 17):**
- `drivers/gpu/drm/panel/panel-samsung-sofef00.c` — replaced with complete 333-line version from Buildroot

**Note on GEM helpers:** `CONFIG_DRM_GEM_DMA_HELPER=m` and `CONFIG_DRM_GEM_SHMEM_HELPER=m` in sm8150-mainline .config. MSM DRM's Kconfig does NOT `select` these helpers explicitly. The kernel compiles and runs correctly with them as modules — MSM DRM doesn't directly call their symbols. The `sed -i` fixes in .config are not reflected in autoconf.h (make would need to be forced). Not blocking.

### Session 18 — Touchscreen + USB serial (2026-04-25)

**ST FTS touchscreen driver ported and working:**
- Chip: ST FingerSense FTS (`st,fts` compatible), i2c addr 0x49, IRQ GPIO 122, reset GPIO 12
- Source: `linux-cepheus-q-oss/drivers/input/touchscreen/fts_521/` (7000+ lines + lib)
- Ported to sm8150-mainline (6.11): stripped Android deps, stubbed `fts_proc.c`, fixed 4.14→6.11 API changes
- DTS: `gpi_dma2`, `qupv3_id_2`, pinctrl + FTS node added to `sm8150-xiaomi-cepheus.dts`
- Key fix: `deferred_probe_timeout=30` in cmdline — i2c17's GPI DMA probe was pushing display past 10s deferred timeout
- FTS driver built-in (`CONFIG_TOUCHSCREEN_ST_FTS=y`) in sm8150-mainline kernel
- touch_down_cb listener added to nerveos-shell (`cursor->events.touch_down` was not wired)
- **Result:** event3 "fts" registered, FW VER=0x0045, Start menu opens on tap

**Boot image:** `boot_touch.img` permanently flashed
- Kernel: sm8150-mainline with FTS built-in (LOCALVERSION="", version still shows gebc3d hash due to CONFIG_LOCALVERSION_AUTO)
- DTB: Buildroot DTS + gpi_dma2 + qupv3_id_2 + touch pinctrl + FTS node
- Cmdline: added `deferred_probe_timeout=30`

**USB serial fixed permanently:**
- Root cause: S25usbnet was creating composite gadget (ACM+RNDIS) that Windows couldn't reliably open
- Fix: deleted S25usbnet from rootfs; initramfs g0 gadget (ACM-only) persists through switch_root
- Inittab: `GS0:2345:respawn:/sbin/getty -n -l /bin/sh ttyGS0 115200 vt100` (auto-login)
- COM3 appears on every boot, shell accessible immediately, no USB reinit needed

**Dev workflow (fast UI iteration):**
- Edit nerveos-shell sources on Windows
- `py -3 C:\Windows\Temp\push_ns.py --build` → compile (WSL) + push via COM3 serial (~30s total)
- Or just `py -3 C:\Windows\Temp\push_ns.py` to push already-built binary (~24s)

**Saved artifacts:**
- FTS driver: `/opt/sm8150-mainline/drivers/input/touchscreen/fts_521/`
- DTS: `br2-external/board/cepheus/sm8150-xiaomi-cepheus.dts` (canonical copy)
- Kernel config: `CONFIG_TOUCHSCREEN_ST_FTS=y` added to `kernel-nerveos-mainline.config`
- Boot image: `/opt/boot_touch.img` in WSL

### Future work (not started)
- Design and implement the hive peer protocol (resource advertisement exchange)
- DHT-based internet-wide discovery
- Distributed storage layer (Ceph-lite or custom)
- CPU task offloading protocol
- RAM sharing over network (NBD / RDMA)
- AI-aware scheduler (intent-based resource requests)
- Web UI / status dashboard
- Additional device targets (Raspberry Pi 4, generic x86-64)
- Image signing and verified boot

---

## User Preferences & Working Style

- User makes high-level decisions; delegates all technical choices to Claude
- Prefers working, scaffolded code over explanations
- Wants detailed self-documentation maintained so sessions don't repeat context
- First physical device: Xiaomi Mi 9 (cepheus)

---

## Glossary

| Term | Meaning |
|------|---------|
| hive | The collective of all NerveOS nodes |
| hived | The daemon running on every NerveOS node |
| hive0 | The WireGuard network interface on every node |
| node | A single device running NerveOS |
| enrollment | The process of adding a new node to an existing hive |
| Advertisement | Resource snapshot a node broadcasts to peers |
| br2-external | Buildroot's mechanism for keeping project code separate from Buildroot itself |
