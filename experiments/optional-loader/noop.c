/* SPDX-License-Identifier: AGPL-3.0-or-later
 * Diagnostic probe only. No constructors, dependencies, hooks or feature effects.
 * A debugger can distinguish mapping from entry execution using this counter.
 */
__attribute__((visibility("default"))) volatile unsigned oc_noop_calls;
__attribute__((visibility("default"))) int oc_bootstrap_v1(void)
{
    ++oc_noop_calls;
    return 0;
}
