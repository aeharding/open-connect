# Settings

Change your preferences in Mazda’s own menus. Choices save automatically; use <a href="apply-changes.md">Apply changes</a> to restart Mazda Connect when you’re ready.

<dl class="oc-spec">
  <div>
    <dt>Menu</dt>
    <dd><span class="oc-nav-path" data-walkthrough="open-connect">Settings → System → Open Connect</span></dd>
  </div>
  <div>
    <dt>Default</dt>
    <dd>—</dd>
  </div>
  <div>
    <dt>Impact</dt>
    <dd>Varies by setting</dd>
  </div>
  <div>
    <dt>Applies</dt>
    <dd>Per setting</dd>
  </div>
</dl>

<figure class="oc-screen">
  <div class="oc-screen-frame"><img src="assets/guide/setting-touchscreen-while-driving.png" alt="Open Connect settings showing Touchscreen While Driving, Startup disclaimer, Startup optimizations, CarPlay and Android Auto, and Audio sources." width="800" height="480"></div>
  <figcaption>Open Connect settings (retained 0.3.0-dev.19 capture).</figcaption>
</figure>

## Notes

<p>Fresh installations use the choices listed below; updates keep your choices.</p>

<p>Browsing Settings has no isolated RAM/CPU/startup measurement. Individual settings have different measured effects; see <a href="#impact-at-a-glance">Impact at a glance</a>.</p>

<p>Each setting page explains the affected features and any startup delay.</p>

<p>Choices save automatically. Use <a href="apply-changes.md">Apply changes</a> to restart Mazda Connect and activate them; <a href="uninstall.md">Uninstall</a> restarts automatically and <a href="about.md">About</a> is read-only.</p>

<p><a href="performance.md">Performance evidence</a> records published dev.20 cold ACC-off results and the separate n=1 toggle sweep. Apply changes and Settings Uninstall have bench verification; real-car qualification remains pending. <strong>0.3.0-dev.21</strong> is a development prerelease.</p>


<span id="change-a-preference"></span>

## Choose a setting

Open Connect is just above **About** in Mazda’s System menu. Its settings follow this order:

1. [**Touchscreen While Driving**](touchscreen.md): <span class="oc-default oc-default--on">Allow</span> by default; **Factory Default** restores the saved pre-install setting.
2. [**Startup disclaimer**](disclaimer.md): <span class="oc-default oc-default--on">Skip</span> by default; **Show** restores the warning.
3. [**Startup optimizations**](startup-optimizations.md): <span class="oc-default oc-default--off">Off</span> by default.
4. **CarPlay & Android Auto**:
    - [Wireless CarPlay](wireless-carplay.md): <span class="oc-default oc-default--off">Off</span>, unless factory enabled.
    - [Show CarPlay on connection](carplay-on-connection.md): <span class="oc-default oc-default--off">Factory behavior</span> by default (**Factory** in the list); choose **Automatically show** for **Auto**.
    - [Android Auto](android-auto.md): <span class="oc-default oc-default--on">On</span> by default.
5. **Audio sources**:
    - [Pandora](pandora.md): <span class="oc-default oc-default--on">On</span> by default.
    - [SiriusXM](siriusxm.md): <span class="oc-default oc-default--on">On</span> by default.
6. [**Developer options**](developer-options.md): <span class="oc-default oc-default--off">UART Off; SSH Off</span>; no public key imported.
7. [**Apply changes**](apply-changes.md): restart to activate saved choices; disabled when there are no pending changes.
8. [**Uninstall**](uninstall.md)
9. [**About**](about.md)

In the dev.21 North American prerelease, [DVD](dvd.md) is folded into **Startup optimizations**. The earlier dev.20 release has a separate DVD toggle. Older configurations migrate automatically, keeping your Startup optimizations choice and remaining preferences. The [Pandora](pandora.md) and [SiriusXM](siriusxm.md) pages show newly qualified PR #149 captures matching that two-row menu; unchanged dev.19 screenshots and dev.20 videos retain their capture identities.

## Impact at a glance

RAM and CPU differences below are **versus Stock**, on published **v0.3.0-dev.20**; additional Home comparisons against Base=0 are labeled. Stock used disclaimer **Show**; installed boots used **Skip**, so total Home gains include that difference. **Base=0/1** means Startup optimizations off/on. Service RAM labels describe switching the named integration off; “avail” means the proxy defined below. CPU differences are **percentage points (pp)** of total two-core capacity. Primary Base medians have **n=3** clean cold ACC-off traces per condition; isolated toggles are a **separate n=1 sweep**, compared with the earlier control medians.

**Open Connect Base=0 baseline:** Home **35.6 s** versus Stock **39.9 s**, **+0.6 MiB available proxy**, **+0.7 pp boot CPU** and **396 KiB own allocated tmpfs** versus none on Stock. This does not establish zero overhead; **#9 remains open**.

| Setting / configuration | Home vs Stock Show | Available proxy vs Stock | Boot CPU vs Stock | Trade-off / limits |
| --- | --- | --- | --- | --- |
| [Touchscreen While Driving](touchscreen.md) | Not measured separately | Not measured separately | Not measured separately | Touch stays available while moving. |
| [Startup disclaimer Skip](disclaimer.md) | ~4.3 s earlier in Base=0 | Not isolated | Not isolated | Whole Base=0 Skip vs Stock Show comparison; no isolated disclaimer wait measured. |
| [Startup optimizations on](startup-optimizations.md), n=3 | ~7.7 s earlier; ~3.4 s beyond Base=0 Skip | +21.2 MiB; AnonPages −17.8 MiB | −4.8 pp | Unused services stop; Navigation delay with the saved Wireless override. |
| [Wireless CarPlay on](wireless-carplay.md), n=1 | ~5.1 s earlier; ~0.8 s vs Base=0 | ~0 MiB (+0.1 observed) | +2.2 pp; settled +3.4 pp | Connected iPhone, Home workload; pairing and compatible hardware required. |
| [Show CarPlay on connection](carplay-on-connection.md) | Not measured separately | Not measured separately | Not measured separately | CarPlay may replace your current screen; tests held Factory. |
| [Android Auto off](android-auto.md), n=1 | ~4.7 s earlier; ~0.4 s vs Base=0 | +4.6 MiB | +0.9 pp | Built-in Android Auto becomes unavailable. |
| [Pandora off](pandora.md), n=1 | ~3.9 s earlier; 0.4 s later vs Base=0 (one trial; repeatability unknown) | +1.9 MiB | +2.4 pp | Mazda’s Pandora integration disappears; CarPlay apps still work. |
| [SiriusXM off](siriusxm.md), n=1 | ~5.5 s earlier; ~1.2 s vs Base=0 | +7.4 MiB | −0.6 pp | Satellite radio and SiriusXM data become unavailable. |
| Max-off combined preset, n=1 | **29.0 s Home**, ~10.9 s earlier | **+36.7 MiB** | **−4.3 pp** | Base=1; Android Auto, Pandora, SiriusXM and Wireless off. Removes optional features; gains are not additive. |
| [Developer options](developer-options.md) | Not measured separately | Not measured separately | Not measured separately | Direct access; enabled SSH can start a daemon. |

“Available” is the **MemFree + Buffers + Cached + SReclaimable − Shmem proxy**. **Linux 3.0.35 has no kernel MemAvailable**; the proxy is not guaranteed allocatable RAM. It differs from raw **MemFree** and resident anonymous **AnonPages** (commit accounting is **Committed_AS**). MiB = 1,048,576 bytes. Do not add differences from separate trials.

Startup optimizations delays Navigation about **20 s** only with the **saved Open Connect Wireless CarPlay override** on. An already-checked **factory enabled** row leaves that override off and does not trigger the delay.

[Performance evidence](performance.md#published-dev20-cold-acc-off-comparison-2026-11-25) retains all primary attempts, both failures, timing bounds and named RAM metrics. Its [separate toggle sweep](performance.md#stage-2b-isolated-toggle-sweep-n1) records the single-trial limits. Small timing/CPU differences can reflect background phone/Navigation activity. PR #149’s folded DVD policy and screenshots have separate qualification; the published dev.20 numbers are not new measurements of that candidate.

## Apply changes

Select [**Apply changes**](apply-changes.md) above **Uninstall**, then confirm **Restart**. Keep the car on until Mazda Connect restarts. You don’t need a USB drive or computer. The row is disabled when there are no pending changes.

**restart needed** means a choice is saved but not active yet. You can change several settings before applying them together. Saved choices also take effect on the next full startup; a quick ignition off/on may resume the same session. If a save cannot be confirmed, reopen Open Connect and check the choice before trying again.

The guide describes the **0.3.0-dev.21 development prerelease** for North American version **74.00.324A**. This build awaits its USB-insertion and installer-launch bench retest. Real-car qualification remains pending.
