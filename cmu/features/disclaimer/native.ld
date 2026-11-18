/* SPDX-License-Identifier: AGPL-3.0-or-later
 * Exact 55.00.750B NA addresses. The CMU verifies the original SHA-256 first.
 * Only our compiled code and replacement words are emitted, never OEM bytes.
 */
cmu_stock_process = 0x4b8c;
cmu_system = 0x4c88;
cmu_copy = 0x4f04;
cmu_log_allowed = 0x4fb8;
cmu_log_write = 0x5120;
cmu_uia_handle = 0x6914;
cmu_focused_app = 0x4dd8;
cmu_stop_service = 0x187d4;
cmu_image_base = 0;
SECTIONS {
    .sizes 0x44 : { *(.sizes) }
    .branch 0x7ed4 : { *(.branch) }
    .payload 0x48c00 : {
        *(.text)
        . = ALIGN(4);
        *(.rodata.str1.1)
        __payload_end = .;
    }
    /DISCARD/ : { *(.ARM.exidx*) *(.ARM.attributes) *(.comment) *(.note*) }
}
ASSERT(SIZEOF(.payload) <= 1024, "native code exceeds the verified padding")
ASSERT(SIZEOF(.sizes) == 8 && SIZEOF(.branch) == 4, "invalid patch words")
