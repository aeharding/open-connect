# Services

The former Services controls now have individual pages. Start with [Settings](settings.md) for all fresh-install defaults and restart guidance. The [Pandora](pandora.md) and [SiriusXM](siriusxm.md) screenshots show the earlier Audio sources menu without a DVD row (predating [Source order](source-order.md) in **0.3.0-dev.27**); earlier retained dev.19 screenshots and dev.20 walkthroughs predate both changes.

<span id="base-optimizations"></span>

## Startup optimizations

[Startup optimizations](startup-optimizations.md), previously **Base optimizations**, reduces background logging and unused services. It defaults to **Off**. Your saved choice is kept; Android Auto and the audio-source choices stay independent.

<span id="phone-and-entertainment"></span>

## CarPlay & Android Auto

Open **<span class="oc-nav-path" data-walkthrough="phone-connections">Mazda Settings → System → Open Connect → CarPlay &amp; Android Auto</span>**.

- [Wireless CarPlay](wireless-carplay.md)
- [Show CarPlay on connection](carplay-on-connection.md)

### Android Auto

[Android Auto](android-auto.md) controls built-in Android Auto support. It defaults to **On**.

## Audio sources

Open **<span class="oc-nav-path" data-walkthrough="audio-sources">Mazda Settings → System → Open Connect → Audio sources</span>** for [Source order](source-order.md), **Pandora** and **SiriusXM**. Disabled integrations disappear from Mazda’s Sources list after restart. In **0.3.0-dev.27**, [DVD](dvd.md) is folded into Startup optimizations; older configurations migrate automatically. The earlier dev.20 release has a separate DVD toggle. Audio CDs still work.

### Pandora

[Pandora](pandora.md) controls Mazda’s built-in Pandora integration. It defaults to **On**; CarPlay and Bluetooth audio stay independent.

### SiriusXM

[SiriusXM](siriusxm.md) controls satellite radio and SiriusXM data. It defaults to **On**.

## Testing

These are development controls for **74.00.324A NA/cmu150_NA**. Published **0.3.0-dev.20** has [matched cold ACC-off Stock/Base cohorts and a separate n=1 toggle sweep](performance.md#published-dev20-cold-acc-off-comparison-2026-11-25). Later bench checks covered same-version Reinstall, DVD policy/migration, Source order, and Settings Uninstall without adding a new performance cohort. Real-car checks, Android-phone use and equipped SiriusXM playback remain unqualified.

Each setting page links its evidence and limits. Total Home gains versus Stock Show include disclaimer Skip; they do not establish zero boot/CPU/RAM overhead.
