# Optional-loader probe

**The scoped loader entry passed in a one-shot composed startup.** A copied
MMUI plugin loaded our marker module; the next baseline boot used the original
plugin without it. This is an adapter proof for
[#25](https://github.com/aeharding/open-connect/issues/25), not a product runtime.
See [the combined experiment](../boot-selection/README.md#composed-startup).

The target [adapter](../../cmu/adapters/fw55/mmui-loader.S) replaces the final
zero-return instruction in the exact FW55 mmuiLoadUias function with a call into
the verified 200-byte segment gap. It uses existing dlopen/dlsym imports to
call oc_bootstrap_v1(), then resumes the
unchanged epilogue with the original zero return value. The default host probe uses
/data/open-connect/bootstrap-v1.so; the composition supplies its checked generation
path at build time. Mazda's application setup,
focus registrations and subsequent AppsLoadingFinish call remain in place.

Missing library or symbol skips the entry. A constructor/entry crash or hang is
**not** caught. A library opened without its entry remains mapped. The bootstrap
is trusted installed code; this hook does not authenticate it, consume trial
state, load optional features or implement paired readiness.

noop.c is only a diagnostic bootstrap: no constructors, dependencies or hooks.
Its exported counter distinguishes loading from invocation in a test/debugger.
A mapping alone is not proof that its entry ran.

## Build and check

Install the host package as described in [CONTRIBUTING](../../CONTRIBUTING.md).
Clang must support ARM; LLVM LLD is needed for the shared-library cross-build.

~~~sh
python -m unittest discover -s experiments/optional-loader -v
OC_LLD=/usr/bin/ld.lld python -m unittest discover -s experiments/optional-loader -v

python experiments/optional-loader/build.py \
  --original /private/path/svcjcimmui.so \
  --output runs/loader-probe
~~~

The first command skips the ARM shared-library check when OC_LLD is unset.
Linux CI runs five checks (including a generation path fitting the RX gap): ARM branch relocation at three load bases,
unknown-base refusal, real host loader invocation, and an ARM shared probe without
DT_NEEDED or constructors. They do not execute the ARM hook or Mazda's loader.
Private original SHA256:
2c2c0494817b13a38c36a8276a39899b4096efc217e82568fe3842f8b34bb025.
Generated OEM/candidate bytes are restricted to ignored runs/ or backups/.

The combined trial supplied checked immutable files, one-attempt control and
independent undo before selection. Its native marker verified both entry and the
actual logging policy; separate JS and visual checks verified the GUI path.
The default standalone probe still provides no install command or live profile.
See [loader findings](../../docs/reverse-engineering.md#optional-extension-loading).
