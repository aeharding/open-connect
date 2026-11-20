/* SPDX-License-Identifier: AGPL-3.0-or-later */
.syntax unified
.arm
.section .sizes,"a"
.word __payload_end
.word __payload_end
.section .branch,"ax"
bl cmu_native_process

/* Replacement metadata words only. See layout.txt for their file destinations.
 * Preserve every original virtual address and shift the original file tail
 * from offset 0x6f79c by one segment alignment (0x8000). */
.section .layout,"a"
.word 0x8af08
.word 0x7779c
.word 0x777dc
.word __payload_end - 0x5c900
.word 0x7779c, 0x777a0, 0x777a4, 0x777a8
.word 0x777dc, 0x77994, 0x77d44, 0x8add4
.word 0x8add4, 0x8ae07, 0x8ae2e, 0x8b318, 0x9c338
