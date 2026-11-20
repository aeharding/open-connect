/* SPDX-License-Identifier: AGPL-3.0-or-later
 * Exact 74.00.324A NA addresses. The CMU verifies the original SHA-256 first.
 * Only our compiled code and replacement words are emitted, never OEM bytes.
 */
cmu_stock_process = 0x6aac;
cmu_copy = 0x6f74;
cmu_log_allowed = 0x7064;
cmu_log_write = 0x7220;
cmu_uia_handle = 0x8768;
cmu_focused_app = 0x6e00;
cmu_stop_service = 0x2dd88;
cmu_image_base = 0;
SECTIONS {
    .sizes 0x44 : { *(.sizes) }
    .layout 0x1000 : { *(.layout) }
    .branch 0xbfb4 : { *(.branch) }
    .payload 0x6f79c : {
        *(.text)
        . = ALIGN(4);
        *(.rodata.str1.1)
        __payload_end = .;
    }
    /DISCARD/ : { *(.ARM.exidx*) *(.ARM.attributes) *(.comment) *(.note*) }
}
/* Original virtual addresses stay fixed; composition moves the file tail by
 * one 0x8000-aligned interval before appending this code to the RX mapping. */
ASSERT(__payload_end <= 0x70000, "native code exceeds the verified RX address gap")
ASSERT(SIZEOF(.sizes) == 8 && SIZEOF(.branch) == 4, "invalid patch words")
ASSERT(SIZEOF(.layout) == 68, "invalid exact-base layout data")
