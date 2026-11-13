# Disclaimer approaches and the missing loading indicator

Comparison on 55.00.750B, 2026-11-13.

The adapted piotrmocko/mzd-v74-tweaks feature successfully bypassed the visible
warning in the observed demo, but the user still saw a black transition. Our
native-plus-JS version also retained a visible fade. Neither has demonstrated a
seamless startup.

| Question | GitHub adaptation | Our current independent approach |
| --- | --- | --- |
| Intervention | Replace Disclaimer UI with transparent NoCtrl template; send DisposeIntroVideo then Global.Yes from ready | Intercept native ShowDisclaimer from IntroAnimation and reuse the automatic Timeout decision rules; JS releases intro after transition |
| Native decision | Manual acknowledgement route, eight rules | Automatic-timeout route, nine rules including WasDisplayOff |
| Scope | Disclaimer context whenever reached; other boot paths not yet tested | Exact Intro/system-focus/native-state guards; unsupported paths remain stock |
| Maintenance | One JS file; smaller and easier to inspect | Native addresses, ABI/PIC patch plus JS hook; more firmware-specific work |

These are behavioral differences, not proof that either route is generally
better. Last-app, navigation, audio, display-off and resume require testing beyond
the observed Home case. The source comparison used upstream commit
5a17963a8631b3b68b9187b6ebbefeef1def05ef. Our v55 adaptation omits the v74-only
NotifyDisclaimerEnd event and uses our independent publication/undo tools, not
the upstream installer. It does not establish unmodified v74 behavior.

## Actual handoff timing

In the comparison demo CMU log clock, DisposeIntroVideo arrived at 26.286s,
Global.Yes routed at 26.372s, and TRANLOGOEND_SURFACE unregistered at 26.393s.
Disclaimer-to-Home Crossfade began at 26.635s and completed at 27.299s.
The ending logo therefore disappeared about 0.906s before transition completion.
This supports early surface disposal as one contributor; it is not a pixel
measurement of the black interval.

Our latest watched run completed Home transition at 27.490s and received
DisposeIntroVideo at 27.501s. It still visibly faded. Both runs logged the
missing named transition for Startup / Ending.Home and defaulted to Crossfade.
Consequently, delaying disposal alone does not settle the remaining visual
behavior; the actual transition and surface ownership are the next useful target.

## Loading indicator

Exact native source establishes a separate QuickStartLoop context. A transition
toward NORMAL from states 3, 4 or 5 can emit ShowQuickStartLoop, subject to the
acknowledgement guard. Only particular current contexts enter QuickStartLoop;
its entry starts quicktranlogo. Other contexts acknowledge without entering it.

This demo followed IntroAnimation and initial state1-to-NORMAL instead.
quicktranlogo was already stopped. There is also an early LOOPLOGO_SURFACE,
distinct from QUICKTRANLOGO_SURFACE and the intro-ending surface. We have not
identified which asset matches the loading indicator the user remembers.
A software reboot is not representative of every standby/ending/ACC path, and
these findings do not establish that an indicator is cold-boot-only.

## Recommendation and next question

Keep the simpler GitHub-style implementation as a serious candidate. Native
placement alone does not make our solution more correct. The independent native
work remains useful for retaining automatic continuation semantics and exposing
the actual startup state machine.

Next, trace the known Startup / Ending.Home fallback and surface visibility
through Crossfade, then make the smallest justified transition/handoff change.
Do not tune timers, mask pixels, or add another installation framework. Compare
the result on the bench; choose the implementation from behavior and maintenance
cost rather than its implementation layer.

Current bench: stock native loaded; adapted comparison JS installed and loaded;
root read-only. Repeat demo succeeded, UART/camera handles closed. No new target
changes were made for this analysis.

Evidence:
- runs/mzd-v74-tweaks-comparison/analysis/result.json
- Same directory: comparison-lifecycle-lines.bin, our-lifecycle-lines.bin,
  quickstart-native-slices.txt, quickstart-cells.json.
- runs/mzd-v74-tweaks-comparison/watch-user/{final.json,comparison-result.json,host-cleanup.json}
- Upstream: https://github.com/piotrmocko/mzd-v74-tweaks/tree/5a17963a8631b3b68b9187b6ebbefeef1def05ef
