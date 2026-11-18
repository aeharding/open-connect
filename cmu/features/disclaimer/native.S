/* SPDX-License-Identifier: AGPL-3.0-or-later */
.syntax unified
.arm
.section .sizes,"a"
.word __payload_end
.word __payload_end
.section .branch,"ax"
bl cmu_native_process
