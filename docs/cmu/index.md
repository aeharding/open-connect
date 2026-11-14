# Understand the Mazda CMU

The CMU is the infotainment computer behind first-generation Mazda Connect.
Our research follows the path from startup policy through native services to
the screen, so a patch changes the component that owns the behavior.

These notes describe **55.00.750B North America** unless a page says otherwise.
They are engineering findings, not a complete firmware specification.

## Software layers

| Layer | Role in the paths we have traced | Read more |
| --- | --- | --- |
| Linux and vendor init | Mount filesystems and launch startup scripts | [Startup ordering](../reverse-engineering.md#startup-selection-and-reset-evidence) |
| Service Manager (SM) | Start services according to dependencies and supervise their health | [Reset and watchdog evidence](../reverse-engineering.md#startup-selection-and-reset-evidence) |
| Native MMUI and system UIA | Choose application contexts, focus and startup continuation | [Disclaimer decision and cleanup](../reverse-engineering.md#disclaimer-and-intro-handoff) |
| Opera and the JavaScript GUI framework | Render templates and run transitions, callbacks and the frontend heartbeat | [Frontend lifecycle](../reverse-engineering.md#spinner-and-frontend-lifecycle) |
| Audio Manager and SYSTEM | Own audio availability and apply startup policy | [Entertainment without a TAU](../reverse-engineering.md#silent-entertainment-without-a-tau) |

**TAU** means tuner and amplifier unit. Our silent UI bench can exercise some
Entertainment screens without one; that does not establish working playback.

## Questions the research answers

- [Why does moving the disclaimer timer not prevent rendering?](../reverse-engineering.md#disclaimer-and-intro-handoff)
- [Why can replacing a mapped library prevent a read-only remount?](../reverse-engineering.md#loaded-libraries-and-read-only-remount)
- [Where could optional code enter the native and JS layers?](../reverse-engineering.md#optional-extension-loading)
- [Where could a boot configuration be selected before its consumers start?](../reverse-engineering.md#startup-selection-and-reset-evidence)

The [Open Connect architecture](../extension-architecture.md) proposes how to use
these boundaries. A proposed recovery policy is not an observed Mazda guarantee.

## What is still open

We have not demonstrated a complete automatic fallback after a modified boot
fails. Reset-cause classification, a trustworthy normal-session-end signal,
cold/ACC behavior, and the effects of different JS and native faults still need
qualification. Existing source traces and bench results identify parts of that
chain; they do not prove the whole recovery lifecycle.

## Contribute a finding

Record the firmware and component, the question, the observed behavior or exact
source basis, and what remains untested. Summarize relevant source rather than
uploading full OEM files. [Documentation guidance](../documentation.md) explains
where to put the result and how to preview it.
