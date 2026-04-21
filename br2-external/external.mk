include $(sort $(wildcard $(BR2_EXTERNAL_NERVEOS_PATH)/package/*/*.mk))

# host-libffi 3.4.4 tramp.c fails with newer GCC (open_temp_exec_file undeclared)
HOST_LIBFFI_CONF_OPTS += --disable-exec-static-tramp

# Xiaomi cepheus-q-oss kernel has many Android vendor drivers that emit
# warnings treated as errors by GCC 12+. Suppress all -Werror for kernel build.
# KCFLAGS is passed via LINUX_MAKE_ENV in linux.mk (line 180) — must override there.
LINUX_MAKE_ENV += KCFLAGS="-Wno-error -Wno-attribute-alias -Wno-strict-prototypes -Wno-designated-init -Wno-format"
