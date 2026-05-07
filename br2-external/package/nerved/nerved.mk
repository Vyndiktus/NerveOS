################################################################################
#
# nerved — NerveOS mesh daemon
#
################################################################################

NERVED_VERSION = 0.1.0
NERVED_SITE = $(TOPDIR)/../nerved
NERVED_SITE_METHOD = local
NERVED_LICENSE = MIT

NERVED_GOMOD = NerveOS/nerved
NERVED_BUILD_TARGETS = cmd/nerved
NERVED_BIN_NAME = nerved

define NERVED_INSTALL_TARGET_CMDS
	$(INSTALL) -D -m 0755 $(@D)/bin/nerved $(TARGET_DIR)/usr/bin/nerved
	$(INSTALL) -D -m 0644 $(BR2_EXTERNAL_NERVEOS_PATH)/package/nerved/nerved.init \
		$(TARGET_DIR)/etc/init.d/S99nerved
endef

$(eval $(golang-package))
