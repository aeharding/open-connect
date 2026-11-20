/* SPDX-License-Identifier: AGPL-3.0-or-later */
/* Replacement data for the exact v74 MMUI plugin. Never contains OEM bytes. */
.syntax unified
.arm
.section .mmui_path,"a"
path_start:
.asciz "/tmp/open-connect/feature/mmui.xml"
path_end:
.section .mmui_sizes,"a"
.word 0x3dc4 + path_end - path_start
.word 0x3dc4 + path_end - path_start
.section .mmui_length,"a"
.word 0xe3a02000 + path_end - path_start
.section .mmui_pointer,"a"
.word 0x3dc4 - 0x29c4
.section .mmui_count-pointer,"a"
.word 0x3dc4 - 0x1bcc
