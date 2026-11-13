# Bench audio plan review — 2026-11-13

One ephemeral reviewer inspected saved OEM code and boot evidence. No hardware,
network acquisition, implementation or additional reviewer was used.

- Mazda's audioMgr test menu calls enableStatus/enable. The actual enable handler
  updates the state owner and notifies HMI/app clients. Reuse that API.
- SYSTEM supplies missing-TAU startup policy after Audio Manager appears. MMUI
  subscribes to the resulting state. Service availability is too early as the
  sole startup guard; no persistent hook was verified.
- Replies precede updates; same-value requests do not send notifications. Read
  back status rather than treating an empty reply as completed activation.
- Runtime disable abandons focus and clears audio session fields. It is an explicit
  bench action, not restoration of every prior setting or session.
- A waiting activation must serialize with profile disable. Service-owner changes
  invalidate the attempt and any recorded runtime ownership.
- Prefer the existing host entry point for the first helper implementation, then
  establish the actual startup hook. No always-running enforcer is needed.

Saved source references (private, not redistributed):
- runs/open-connect-tau-bypass/enable-source/result.bin:
  audioMgr.lua listing 3067–3097, 7729–7895.
- runs/open-connect-snap55/boot-C/rx.bin:
  Audio Manager ready 14.297s, SYSTEM policy 14.316s, Normal state 25.038s.
  This is ordering evidence, not a demonstrated overwrite of an override.
- runs/20261113-t12-mmui-static/system-disassembly.txt:
  UIA_SYSTEM_BLM_AudioManager_Connect_cb, AM_notify_cb,
  UIA_SYSTEM_AudioSourceManager_notifyAudioStatusUpdated.
- runs/open-connect-tau-bypass/{enable,disable}/result.bin:
  live API effect and explicit disable behavior.

Findings are incorporated into PLAN.md. Full reviewer output remains private at
runs/bench-profile-review/review.md. Primary developer retains ownership.
