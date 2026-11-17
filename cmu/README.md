# CMU code

Source that runs on the device when a feature is explicitly tried.

- features/disclaimer/: the native startup change.
- features/touch/setting.sh: read the v55 display restriction or change it from a
  known value. The installer must save the value before install. Uninstall can
  restore `absent`, `enable` or `disable`. The display service reads it at startup.
- installer/dialog.js: `OpenConnectInstaller.choose(framework, installed, onChoice)`
  opens Mazda’s dialog at Home. It reports `install`, `uninstall` or `cancel`
  once. A successful call returns a cancel function for USB removal. A busy GUI
  returns false. The caller owns the device transaction.
- adapters/fw55/: frontend and native integration for 55.00.750B NA.
- startup/: one-shot selection, readiness, checked flush and file-publication templates.

Host builders live in tooling/open_connect/firmware55. They compose these sources
with privately supplied OEM files; this directory contains no OEM firmware.
