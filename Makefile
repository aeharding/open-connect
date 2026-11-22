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

ARM_FLAGS = --target=armv7-linux-gnueabi -marm -mfloat-abi=soft -Os \
    -ffreestanding -fno-stack-protector -fno-unwind-tables \
    -fno-asynchronous-unwind-tables -nostdlib -static -Wall -Wextra -Werror
LINK_FLAGS = --ld-path=$(LLD) -Wl,-e,_start,--build-id=none,-z,max-page-size=4096,--strip-all
NATIVE_FLAGS = --target=armv7-none-eabi -march=armv7-a -marm -mfloat-abi=hard \
    -mfpu=vfpv3 -Oz -ffreestanding -fPIC -fvisibility=hidden \
    -fno-unwind-tables -fno-asynchronous-unwind-tables -fno-stack-protector

.PHONY: release native check-ui
release: native $(OUT)/api $(OUT)/flush $(OUT)/boot-select $(addprefix $(OUT)/mmui-,path.bin sizes.bin length.bin pointer.bin count-pointer.bin)
	sh tooling/package-usb.sh "$(OUT)"

native: $(OUT)/native.bin $(OUT)/branch.bin $(OUT)/sizes.bin $(OUT)/layout.bin

check-ui:
	node tests/fixtures/installer-es5.js cmu/installer
	node tests/fixtures/installer-dialog.js cmu/installer/dialog.js
	node tests/fixtures/installer-settings.js cmu/installer/dialog.js cmu/installer/settings.js
	node tests/fixtures/installer-runtime.js cmu/installer/runtime.js
	node tests/fixtures/usb-loader.js cmu/installer/loader.js

$(OUT):
	mkdir -p "$@"

$(OUT)/api: cmu/installer/api.c | $(OUT)
	$(CLANG) $(ARM_FLAGS) $(LINK_FLAGS) "$<" -o "$@"

$(OUT)/flush: cmu/startup/flush.c | $(OUT)
	$(CLANG) $(ARM_FLAGS) $(LINK_FLAGS) "$<" -o "$@"

$(OUT)/boot-select: cmu/installer/boot-select.c cmu/installer/boot-policy.h cmu/installer/boot-system.h cmu/installer/boot-plan.h cmu/installer/boot-io.h cmu/installer/boot-hash.h | $(OUT)
	$(CLANG) $(filter-out -Os,$(ARM_FLAGS)) -O2 $(LINK_FLAGS) "$<" -o "$@"

$(OUT)/mmui.o: cmu/installer/mmui.S | $(OUT)
	$(CLANG) --target=armv7-none-eabi -marm -c "$<" -o "$@"

$(OUT)/mmui-%.bin: $(OUT)/mmui.o
	$(OBJCOPY) -O binary --only-section=.mmui_$* "$<" "$@"

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
