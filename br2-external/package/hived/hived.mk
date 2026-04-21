################################################################################
#
# hived — NerveOS mesh daemon
#
################################################################################

HIVED_VERSION = 0.1.0
HIVED_SITE = $(TOPDIR)/../hived
HIVED_SITE_METHOD = local
HIVED_LICENSE = MIT

HIVED_GOMOD = NerveOS/hived
HIVED_BUILD_TARGETS = cmd/hived
HIVED_BIN_NAME = hived

define HIVED_INSTALL_TARGET_CMDS
	$(INSTALL) -D -m 0755 $(@D)/bin/hived $(TARGET_DIR)/usr/bin/hived
	$(INSTALL) -D -m 0644 $(BR2_EXTERNAL_NerveOS_PATH)/package/hived/hived.init \
		$(TARGET_DIR)/etc/init.d/S99hived
endef

$(eval $(golang-package))
