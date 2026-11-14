# Optional-loader probe

**Host-built, not installed or bench-qualified.** First native loading probe for
[#25](https://github.com/aeharding/open-connect/issues/25), not the optional-feature
runtime or another disclaimer candidate.

The target [adapter](../../cmu/adapters/fw55/mmui-loader.S) replaces the final
zero-return instruction in the exact FW55 mmuiLoadUias function with a call into
104 bytes of verified segment padding. It uses existing dlopen/dlsym imports to
call oc_bootstrap_v1() in /data/open-connect/bootstrap-v1.so, then resumes the
unchanged epilogue with the original zero return value. Mazda's application setup,
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
Linux CI runs all four checks: ARM branch relocation at three load bases,
unknown-base refusal, real host loader invocation, and an ARM shared probe without
DT_NEEDED or constructors. They do not execute the ARM hook or Mazda's loader.
Private original SHA256:
2c2c0494817b13a38c36a8276a39899b4096efc217e82568fe3842f8b34bb025.
Generated OEM/candidate bytes are restricted to ignored runs/ or backups/.

No install command or live profile is provided. Before the bench trial, finish
one-attempt control and independent undo, establish storage/parent access at the
loading point, and verify entry execution as well as mapping. The renderer has a
separate existing developer-script slot; its readiness cannot be inferred from
this native probe. See [loader findings](../../docs/reverse-engineering.md#optional-extension-loading).
