################################################################################
#
# nerved — NerveOS mesh daemon
#
################################################################################

HIVED_VERSION = 0.1.0
HIVED_SITE = $(TOPDIR)/../nerved
HIVED_SITE_METHOD = local
HIVED_LICENSE = MIT

HIVED_GOMOD = NerveOS/nerved
HIVED_BUILD_TARGETS = cmd/nerved
HIVED_BIN_NAME = nerved

define HIVED_INSTALL_TARGET_CMDS
	$(INSTALL) -D -m 0755 $(@D)/bin/nerved $(TARGET_DIR)/usr/bin/nerved
	$(INSTALL) -D -m 0644 $(BR2_EXTERNAL_NERVEOS_PATH)/package/nerved/nerved.init \
		$(TARGET_DIR)/etc/init.d/S99nerved
endef

$(eval $(golang-package))
