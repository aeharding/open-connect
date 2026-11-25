# DVD

The published **v0.3.0-dev.19** and **v0.3.0-dev.20** prereleases expose a separate **DVD** setting under **Audio sources**.

In the upcoming development candidate, DVD is folded into [Startup optimizations](startup-optimizations.md) on North American units running **74.00.324A NA**. Its Audio sources menu contains **Pandora** and **SiriusXM** only.

Enabling Startup optimizations also turns off Mazda’s unused DVD service. Turning it off restores the stock service startup policy; Mazda’s [regional gate](reverse-engineering.md#dvd-hardware-and-regional-gating-offline-v74-na-analysis) still excludes North America from DVD playback. Audio CDs and CarPlay still work.

Older configurations migrate automatically. Your Startup optimizations choice and remaining preferences are kept; the former DVD choice is retired.

The migration and folded policy have offline checks only. Updated screenshots and live upgrade qualification remain pending.

[Back to Settings](settings.md)
