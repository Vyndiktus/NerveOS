# NerveOS — Project Intelligence Document

This file is automatically loaded by Claude Code. Keep it updated after every significant session.
Last updated: 2026-04-21 (session 7 — boot splash logo working automatically, permanently flashed v30)

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
- NerveOS-dev-01 container: VMID 110, IP 10.1.0.36, Debian 12 (SSH alias `NerveOS-dev-01`)

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
- [x] NerveOS-dev-01 LXC container on Proxmox (10.1.0.36) — hived tested and running
- [x] Proxmox API token configured (`root@pam!NerveOS`)

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

### Immediate next steps — rootfs build (session 7 prep)
- [x] Permanently flash boot splash image: `boot_nerveos_v30.img` flashed to boot partition (session 7)
- [x] Naming cleanup: defconfig renamed to `NerveOS_cepheus_defconfig`, Makefile/build script updated
- [x] `mdev -d &` added to init — fixes sda31 not appearing (UFS probes async, mdev -s is one-shot)
- [x] DRM config options added to `kernel-nerveos-mainline.config`
- [ ] **Run first Buildroot build** — clone Buildroot in WSL2, run `nerveos-build.sh`
- [ ] **Verify rootfs boots** — sda31 pivot should now work with mdev daemon fix
- [ ] Test WireGuard (`hive0` interface) on the device via USB serial
- [ ] Test hived daemon startup over serial console

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
