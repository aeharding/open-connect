# SPDX-License-Identifier: AGPL-3.0-or-later
# Public build: no Python, OEM files, installed oc package or connected CMU.
OUT ?= runs/build
CLANG ?= clang
LLD ?= ld.lld
OBJCOPY ?= llvm-objcopy
NATIVE_DIR ?= cmu/features/disclaimer
ifeq ($(shell uname -s),Darwin)
LLD := $(or $(shell command -v $(LLD)),$(wildcard /opt/homebrew/opt/lld/bin/ld.lld))
OBJCOPY := $(or $(shell command -v $(OBJCOPY)),$(wildcard /opt/homebrew/opt/llvm/bin/llvm-objcopy))
endif

ARM_FLAGS = --target=armv7-linux-gnueabi -marm -mfloat-abi=soft -Os -fno-pic -fvisibility=hidden \
    -ffunction-sections -fdata-sections -ffreestanding -fno-stack-protector \
    -fno-unwind-tables -fno-asynchronous-unwind-tables -nostdlib -static -Wall -Wextra -Werror
THUMB_FLAGS = --target=armv7-linux-gnueabi -march=armv7-a -mthumb -fomit-frame-pointer -mfloat-abi=soft \
    -Oz -mllvm -enable-machine-outliner -fno-builtin -fno-pic -fvisibility=hidden -ffunction-sections -fdata-sections -ffreestanding \
    -fno-stack-protector -fno-unwind-tables -fno-asynchronous-unwind-tables -nostdlib -static \
    -Wall -Wextra -Werror
LINK_FLAGS = --ld-path=$(LLD) -Wl,-e,_start,--build-id=none,--gc-sections,--icf=all,-z,max-page-size=4096,--strip-all
SHARED_CORE_SRCS = cmu/installer/core/oc-hash.c cmu/installer/core/oc-io.c \
    cmu/installer/core/oc-manifest.c cmu/installer/core/oc-record.c \
    cmu/installer/core/oc-config.c cmu/installer/core/oc-guard.c
CORE_SRCS = $(SHARED_CORE_SRCS) cmu/installer/core/oc-plan.c \
    cmu/installer/core/oc-store.c cmu/installer/core/oc-boot.c
API_SRCS = cmu/installer/api.c $(SHARED_CORE_SRCS) cmu/installer/core/oc-root.c \
    cmu/installer/core/oc-access.c cmu/installer/core/oc-txn.c \
    cmu/installer/core/oc-render.c cmu/installer/core/oc-api.c
INSTALL_SRCS = cmu/installer/install.c $(SHARED_CORE_SRCS) cmu/installer/core/oc-root.c \
    cmu/installer/core/oc-access.c cmu/installer/core/oc-txn.c \
    cmu/installer/core/oc-render.c cmu/installer/core/oc-compose.c
IGNITION_SRCS = cmu/installer/ignition.c cmu/installer/core/oc-hash.c cmu/installer/core/oc-io.c \
    cmu/installer/core/oc-manifest.c cmu/installer/core/oc-record.c
CORE_HDR = cmu/installer/core/oc-core.h
NATIVE_FLAGS = --target=armv7-none-eabi -march=armv7-a -marm -mfloat-abi=hard \
    -mfpu=vfpv3 -Oz -ffreestanding -fPIC -fvisibility=hidden \
    -fno-unwind-tables -fno-asynchronous-unwind-tables -fno-stack-protector

.PHONY: release native check-ui
release: native $(OUT)/touch-disable.so $(OUT)/api $(OUT)/install $(OUT)/flush $(OUT)/boot-select $(OUT)/ignition $(OUT)/vui-path.bin $(addprefix $(OUT)/mmui-,path.bin sizes.bin length.bin pointer.bin count-pointer.bin)
	sh tooling/package-usb.sh "$(OUT)"

native: $(OUT)/native.bin $(OUT)/branch.bin $(OUT)/sizes.bin $(OUT)/layout.bin

check-ui:
	node tests/fixtures/installer-es5.js cmu/installer
	node tests/fixtures/installer-dialog.js cmu/installer/dialog.js
	node tests/fixtures/installer-settings.js cmu/installer/dialog.js cmu/installer/settings.js
	node tests/fixtures/installer-settings-ux.js cmu/installer/dialog.js cmu/installer/settings.js
	node tests/fixtures/installed-runtime.js cmu/installer
	node tests/fixtures/maintenance-runtime.js cmu/installer
	node tests/fixtures/mixed-maintenance.js cmu/installer
	node tests/fixtures/system-hook.js cmu/installer/system-hook.js
	node tests/fixtures/usb-loader.js cmu/installer/loader.js
	node tests/fixtures/usb-receiver.js cmu/installer
	node tests/fixtures/carplay.js cmu/installer

$(OUT):
	mkdir -p "$@"

$(OUT)/api: $(API_SRCS) $(CORE_HDR) | $(OUT)
	$(CLANG) $(THUMB_FLAGS) $(LINK_FLAGS) $(API_SRCS) -o "$@"
	$(OBJCOPY) --remove-section=.comment --remove-section=.ARM.attributes "$@"

$(OUT)/install: $(INSTALL_SRCS) $(CORE_HDR) | $(OUT)
	$(CLANG) $(THUMB_FLAGS) $(LINK_FLAGS) $(INSTALL_SRCS) -o "$@"
	$(OBJCOPY) --remove-section=.comment --remove-section=.ARM.attributes "$@"

$(OUT)/flush.o: cmu/startup/flush.c $(CORE_HDR) | $(OUT)
	$(CLANG) $(ARM_FLAGS) -c "$<" -o "$@"

$(OUT)/flush-hash.o: cmu/installer/core/oc-hash.c $(CORE_HDR) | $(OUT)
	$(CLANG) $(ARM_FLAGS) -c "$<" -o "$@"

$(OUT)/flush: $(OUT)/flush.o $(OUT)/flush-hash.o | $(OUT)
	$(LLD) -e _start --build-id=none --gc-sections --icf=all -z max-page-size=4096 --strip-all \
	    "$(OUT)/flush.o" "$(OUT)/flush-hash.o" -o "$@"

$(OUT)/boot-select: cmu/installer/boot-select.c $(CORE_SRCS) $(CORE_HDR) | $(OUT)
	$(CLANG) $(THUMB_FLAGS) $(LINK_FLAGS) cmu/installer/boot-select.c $(CORE_SRCS) -o "$@"
	$(OBJCOPY) --remove-section=.comment --remove-section=.ARM.attributes "$@"

$(OUT)/ignition: $(IGNITION_SRCS) $(CORE_HDR) | $(OUT)
	$(CLANG) $(THUMB_FLAGS) $(LINK_FLAGS) $(IGNITION_SRCS) -o "$@"
	$(OBJCOPY) --remove-section=.comment --remove-section=.ARM.attributes "$@"

$(OUT)/mmui.o: cmu/installer/mmui.S | $(OUT)
	$(CLANG) --target=armv7-none-eabi -marm -c "$<" -o "$@"

$(OUT)/mmui-%.bin: $(OUT)/mmui.o
	$(OBJCOPY) -O binary --only-section=.mmui_$* "$<" "$@"

$(OUT)/vui-path.bin: cmu/installer/vui.S | $(OUT)
	$(CLANG) --target=armv7-none-eabi -marm -c "$<" -o "$(OUT)/vui.o"
	$(OBJCOPY) -O binary --only-section=.vui_path "$(OUT)/vui.o" "$@"

$(OUT)/native.o: $(NATIVE_DIR)/native.c | $(OUT)
	$(CLANG) $(NATIVE_FLAGS) -c "$<" -o "$@"

# Preserve source string order so the linker produces the established patch bytes.
$(OUT)/native-ordered.o: $(OUT)/native.o
	$(OBJCOPY) --set-section-flags .rodata.str1.1=alloc,load,readonly,data,contents "$<" "$@"

$(OUT)/words.o: $(NATIVE_DIR)/native.S | $(OUT)
	$(CLANG) --target=armv7-none-eabi -marm -c "$<" -o "$@"

$(OUT)/patch.elf: $(OUT)/native-ordered.o $(OUT)/words.o $(NATIVE_DIR)/native.ld
	$(LLD) -T "$(NATIVE_DIR)/native.ld" --entry=cmu_native_process --build-id=none \
	    -o "$@" "$(OUT)/native-ordered.o" "$(OUT)/words.o"

$(OUT)/native.bin: $(OUT)/patch.elf
	$(OBJCOPY) -O binary --only-section=.payload "$<" "$@"

$(OUT)/branch.bin: $(OUT)/patch.elf
	$(OBJCOPY) -O binary --only-section=.branch "$<" "$@"

$(OUT)/sizes.bin: $(OUT)/patch.elf
	$(OBJCOPY) -O binary --only-section=.sizes "$<" "$@"

$(OUT)/layout.bin: $(OUT)/patch.elf
	$(OBJCOPY) -O binary --only-section=.layout "$<" "$@"

# Empty link-time dependencies supply SONAMEs only. Never package these stubs.
$(OUT)/touch-stubs/empty.o:
	mkdir -p "$(OUT)/touch-stubs"
	$(CLANG) --target=armv7-linux-gnueabihf -x c -c /dev/null -o "$@"

$(OUT)/touch-stubs/svc-com-jci-cpp-devices.so $(OUT)/touch-stubs/libdl.so.2: $(OUT)/touch-stubs/empty.o
	$(LLD) -shared --soname=$(@F) -o "$@" "$<"

# Unwind tables are required: OEM getDevice can throw through this C frame.
$(OUT)/touch-disable.o: cmu/features/touch/disable.c | $(OUT)
	$(CLANG) $(filter-out -fno-unwind-tables -fno-asynchronous-unwind-tables,$(NATIVE_FLAGS)) -funwind-tables -Wall -Wextra -Werror -c "$<" -o "$@"

$(OUT)/touch-disable.so: $(OUT)/touch-disable.o $(OUT)/touch-stubs/svc-com-jci-cpp-devices.so $(OUT)/touch-stubs/libdl.so.2
	set -eu; trap 'rm -f "$@.tmp"' EXIT; \
	$(LLD) -shared --build-id=none --strip-all -z max-page-size=4096 -z now -z norelro --no-rosegment \
	    --disable-new-dtags -rpath /jci/devices:/jci/lib -o "$@.tmp" "$<" \
	    --no-as-needed "$(OUT)/touch-stubs/svc-com-jci-cpp-devices.so" "$(OUT)/touch-stubs/libdl.so.2"; \
	test "$$(wc -c < "$@.tmp")" -le 4096; \
	mv "$@.tmp" "$@"
