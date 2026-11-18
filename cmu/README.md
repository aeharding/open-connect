# CMU code

Source that runs on the device when a feature is explicitly tried.

- features/disclaimer/: the native startup change.
- features/touch/setting.sh: read the v55 display restriction or change it from a
  known value. The installer must save the value before install. Uninstall can
  restore `absent`, `enable` or `disable`. The display service reads it at startup.
- installer/dialog.js: `OpenConnectInstaller.choose(framework, installed, onChoice)`
  opens Mazda’s dialog at Home. It reports `install`, `uninstall` or `cancel`
  once. A successful call returns a cancel function for USB removal. A busy GUI
  returns false. Pass the package version as the fourth argument. After the
  backend verifies installation, call `complete(framework, version, onChoice)`
  for **Done** or **Open settings**.
- installer/usb-launch.sh.in and usb-session.sh: the bounded, RAM-only USB
  bootstrap for v55. Validate and stage a payload, then return immediately to
  Mazda's updater. A short deferred browser call loads the payload in the existing
  document. The payload owns the UI; the bootstrap supplies a session token and
  a bounded loopback reply receiver. usb-preview.js currently shows only Cancel.
  This preview installs no features and leaves no startup hook.
- installer/settings.js: `OpenConnectSettings.fromHome(framework, store, result)`
  opens Mazda Settings and presents the Open Connect list. Register
  `attach(framework, syssettingsApp, store)` once per app instance for the
  System tab entry. The v55 adapter uses Mazda’s List2 template for both pages.
  The owner supplies `read()` and `write(key, expected, requested, reply)`.
  Values are 0 (Mazda default) or 1 (always enable touch or skip the warning).
  The radio changes immediately. Writes run in the background and survive
  leaving the page. Reply with verified values, or null on an uncertain write.
  A fresh read can reconcile an acknowledgement that went missing.
  Load `dialog.js` alongside `settings.js`. About reads `store.version` from the
  installed package. Supply the installer's removal callback as `store.uninstall`
  to enable Uninstall. The view calls it once after confirmation.
- adapters/fw55/: frontend and native integration for 55.00.750B NA.
- startup/: one-shot selection, readiness, checked flush and file-publication templates.

Host builders live in tooling/open_connect/firmware55. They compose these sources
with privately supplied OEM files; this directory contains no OEM firmware.

CI builds both installer views into `installer.js` and runs their interaction tests
against that file. The `fw55-installer-controls` workflow artifact contains the
tested UI, its checksum and license. Standalone USB packaging is tracked in
[issue 7](https://github.com/aeharding/open-connect/issues/7).
