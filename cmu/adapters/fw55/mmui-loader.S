/* SPDX-License-Identifier: AGPL-3.0-or-later
 * 55.00.750B NA svcjcimmui.so: mmuiLoadUias return hook.
 * Replaces only mov r0, #0; resumes the unchanged OEM epilogue.
 * Missing library/symbol returns to stock. This cannot catch a crash or hang.
 */
#ifndef OC_BOOTSTRAP_PATH
#define OC_BOOTSTRAP_PATH "/data/open-connect/bootstrap-v1.so"
#endif
.syntax unified
.arm
.text
.global oc_mmui_load
.type oc_mmui_load, %function
oc_mmui_load:
    push {r4, lr}
    adr r0, library_path
    mov r1, #2                  /* RTLD_NOW, local visibility */
    bl oc_dlopen
    cmp r0, #0
    beq finished
    adr r1, entry_name
    bl oc_dlsym
    cmp r0, #0
    beq finished
    blx r0
finished:
    mov r0, #0                  /* original return value, regardless of init result */
    pop {r4, pc}
.size oc_mmui_load, .-oc_mmui_load
.balign 4
library_path:
    .asciz OC_BOOTSTRAP_PATH
entry_name:
    .asciz "oc_bootstrap_v1"
.balign 4
