################################################################################
#
# python-rns — Reticulum Network Stack
#
################################################################################

PYTHON_RNS_VERSION = 1.1.6
PYTHON_RNS_SOURCE = rns-$(PYTHON_RNS_VERSION).tar.gz
PYTHON_RNS_SITE = https://files.pythonhosted.org/packages/source/r/rns
PYTHON_RNS_SETUP_TYPE = setuptools
PYTHON_RNS_LICENSE = MIT
PYTHON_RNS_LICENSE_FILES = LICENSE

PYTHON_RNS_DEPENDENCIES = python-cryptography python-serial

define PYTHON_RNS_INSTALL_INIT_SYSV
	$(INSTALL) -D -m 0755 $(BR2_EXTERNAL_NerveOS_PATH)/package/python-rns/S60reticulum \
		$(TARGET_DIR)/etc/init.d/S60reticulum
	$(INSTALL) -D -m 0644 $(BR2_EXTERNAL_NerveOS_PATH)/package/python-rns/reticulum.config \
		$(TARGET_DIR)/etc/reticulum/config
endef

$(eval $(python-package))
