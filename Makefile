# NerveOS top-level Makefile
#
# Usage:
#   make setup                  # Clone Buildroot, install host deps
#   make DEVICE=cepheus         # Build image for a device
#   make flash DEVICE=cepheus   # Flash image to connected device
#   make identify               # Identify USB-connected devices
#   make nerved                  # Build nerved daemon (native, for testing)

DEVICE       ?= cepheus
BR_VERSION   ?= 2024.02
BR_DIR       := buildroot
BR_EXT       := $(CURDIR)/br2-external
BUILD_DIR    := build/$(DEVICE)
IMAGES_DIR   := build/images/$(DEVICE)
PYTHON       := python3

.PHONY: all setup buildroot-clone image flash identify nerved clean help

all: image

## setup: Clone Buildroot and prepare the build environment
setup: buildroot-clone
	@echo ""
	@echo "[NerveOS] Setup complete."
	@echo "          Next: make DEVICE=$(DEVICE)"

buildroot-clone:
	@if [ ! -d "$(BR_DIR)" ]; then \
		echo "[NerveOS] Cloning Buildroot $(BR_VERSION)..."; \
		git clone --depth=1 --branch $(BR_VERSION) \
			https://git.buildroot.net/buildroot $(BR_DIR); \
	else \
		echo "[NerveOS] Buildroot already present."; \
	fi

## image: Build a NerveOS image for DEVICE
image: buildroot-clone
	@echo "[NerveOS] Building image for: $(DEVICE)"
	@mkdir -p $(BUILD_DIR) $(IMAGES_DIR)
	$(MAKE) -C $(BR_DIR) \
		BR2_EXTERNAL=$(BR_EXT) \
		O=$(CURDIR)/$(BUILD_DIR) \
		NerveOS_$(DEVICE)_defconfig
	$(MAKE) -C $(BR_DIR) \
		BR2_EXTERNAL=$(BR_EXT) \
		O=$(CURDIR)/$(BUILD_DIR) \
		-j$(shell nproc) \
		2>&1 | tee $(BUILD_DIR)/build.log
	@echo "[NerveOS] Image complete: $(BUILD_DIR)/images/"
	@cp $(BUILD_DIR)/images/*.img $(IMAGES_DIR)/ 2>/dev/null || true

## menuconfig: Open Buildroot menuconfig for DEVICE
menuconfig: buildroot-clone
	$(MAKE) -C $(BR_DIR) \
		BR2_EXTERNAL=$(BR_EXT) \
		O=$(CURDIR)/$(BUILD_DIR) \
		menuconfig

## flash: Flash a pre-built image to a connected device via USB
flash:
	$(PYTHON) tools/nerve-flash.py --device $(DEVICE) $(if $(SERIAL),--serial $(SERIAL),)

## flash-dry: Dry-run flash (no writes)
flash-dry:
	$(PYTHON) tools/nerve-flash.py --device $(DEVICE) --dry-run

## identify: Identify USB-connected devices and match to NerveOS profiles
identify:
	$(PYTHON) tools/nerve-identify.py

## identify-watch: Continuously watch for USB device connections
identify-watch:
	$(PYTHON) tools/nerve-identify.py --watch

## nerved: Build the hive daemon natively (for testing on host)
nerved:
	cd nerved && go build -o ../build/nerved ./cmd/nerved
	@echo "[NerveOS] nerved built: build/nerved"

## nerved-arm64: Cross-compile nerved for ARM64 (cepheus target)
nerved-arm64:
	cd nerved && GOOS=linux GOARCH=arm64 go build -o ../build/nerved-arm64 ./cmd/nerved
	@echo "[NerveOS] nerved built: build/nerved-arm64"

## clean: Remove build artifacts
clean:
	rm -rf build/

## help: Show this help
help:
	@grep -E '^## ' Makefile | sed 's/## /  /'
