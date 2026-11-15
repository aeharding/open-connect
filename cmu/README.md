# CMU code

Source that runs on the device when a feature is explicitly tried.

- features/disclaimer/: the native startup change.
- adapters/fw55/: frontend and native integration for 55.00.750B NA.
- startup/: one-shot selection, readiness, checked flush and file-publication templates.

Host builders live in tooling/open_connect/firmware55. They compose these sources
with privately supplied OEM files; this directory contains no OEM firmware.
