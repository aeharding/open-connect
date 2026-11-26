# DVD

Earlier prereleases (**v0.3.0-dev.19** and **v0.3.0-dev.20**) exposed a separate **DVD** setting under **Audio sources**.

In **0.3.0-dev.24** on North American units (**74.00.324A NA**), DVD is folded into [Startup optimizations](startup-optimizations.md), and **Audio sources** lists **Pandora** and **SiriusXM** only.

Enabling **Startup optimizations** also turns off Mazda’s unused North American DVD service (Mazda’s [regional gate](reverse-engineering.md#dvd-hardware-and-regional-gating-offline-v74-na-analysis) already excludes North America from DVD playback; audio CDs use a separate service and continue to work). Turning it off restores stock startup behavior.

Older configurations migrate automatically, keeping your **Startup optimizations** choice and remaining preferences while retiring the former DVD toggle. No isolated DVD startup or memory benefit is measured separately, and real-car qualification remains pending.

[Back to Settings](settings.md)
