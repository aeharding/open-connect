# Intro handoff

The native bypass keeps Mazda's intro player alive while the GUI builds the next
screen. The paired JavaScript change sends the existing DisposeIntroVideo event
from IntroAnimation's noLongerDisplayed callback, after GuiFramework completes
the transition and hides outgoing native surfaces. It skips the stock Disclaimer
path, whose displayed callback already owns disposal.

No delay, CSS mask, heartbeat change or forced destination is added. The native
nine-rule continuation and original warning/quick-logo exit hooks remain.
Both exact OEM55 originals are required; full sources and candidates stay private.

Host checks execute the real saved BaseApp dispatcher and the same native C
wrapper, plus ARM relocation checks and actual local copy/link/undo transactions.
The JS companion uses the existing linked publication script with per-image
lengths; its cleanup omits only the native MMUI-specific positive mapping test.
The combined boot observer verifies both persistent images before and after
startup using the same serial session.

This is a paired feature: the deferred native variant needs the renderer hook.
Do not install or boot the native half alone. Current experiment evidence lives
under runs/open-connect-smooth; do not replay completed one-shot run directories.
Bench result and final device state are recorded separately in the result note.

## Public checks

After installing the host package, run from the repository root:

~~~sh
.venv/bin/python -m unittest discover -s experiments/intro-handoff -p test_boot.py -v
.venv/bin/python -m unittest discover -s experiments/intro-handoff -p test_publication.py -v
~~~

These exercise paired verification and different-size file publication using
synthetic data and temporary host files. No private firmware or hardware is needed.
The observer passes its paired verifier explicitly; importing it does not replace
the native observer's global verifier.

The JS patch behavior test is separate and still requires privately obtained exact
systemApp.js and BaseApp.js. It is not included in these public checks.
Live dependency validation remains before device access; historical profiles are
not requalified by the import fix. Do not bypass that gate to replay old payloads.
