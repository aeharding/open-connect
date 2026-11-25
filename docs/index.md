<div class="oc-hero">
  <img class="oc-hero-mark" src="assets/brand/logo-mark.svg" alt="" width="72" height="72">
  <div>
    <span class="oc-hero-eyebrow">First-generation Mazda Connect</span>
    <h1>Mazda Open Connect</h1>
    <p>Keep Mazda’s factory look and controls while fixing the daily annoyances — skip the startup disclaimer, keep touch enabled while moving, unlock native wireless CarPlay, and trim unused background services. Everything installs from USB and lives inside Mazda Settings.</p>
    <div class="oc-hero-actions">
      <a class="md-button md-button--primary" href="usb-installer/">Quick start</a>
      <a class="md-button" href="settings/">Explore settings</a>
      <a class="md-button" href="uninstall/">Uninstall</a>
    </div>
  </div>
</div>

<div class="oc-status-strip">
  <span class="oc-status-pill">Pre-release · 74.00.324A NA</span>
  <span>Current development targets exactly <strong>74.00.324A North America (cmu150_NA)</strong>. A qualified release download is not published yet while real-car and physical-input checks remain ahead. <a href="installer-development/">Qualification status →</a></span>
</div>

## What you can customize

Every improvement is optional, lives natively under **Mazda Settings → System → Open Connect**, and can be turned off or uninstalled cleanly without a computer.

<div class="oc-feature-grid">
  <a class="oc-feature-card" href="touchscreen/">
    <div class="oc-feature-head">
      <span class="oc-feature-title">Touchscreen While Driving</span>
      <span class="oc-badge oc-badge--on">Default: Allow</span>
    </div>
    <p class="oc-feature-desc">Removes Mazda’s ~5 mph touchscreen lockout so a passenger can tap menus, maps, or search without stopping the car.</p>
  </a>

  <a class="oc-feature-card" href="disclaimer/">
    <div class="oc-feature-head">
      <span class="oc-feature-title">Startup disclaimer</span>
      <span class="oc-badge oc-badge--on">Default: Skip</span>
    </div>
    <p class="oc-feature-desc">Bypasses the legal warning screen on every start and goes straight to your normal screen while keeping Mazda’s startup flow intact.</p>
  </a>

  <a class="oc-feature-card" href="wireless-carplay/">
    <div class="oc-feature-head">
      <span class="oc-feature-title">Wireless CarPlay</span>
      <span class="oc-badge">Default: Off</span>
    </div>
    <p class="oc-feature-desc">Exposes Mazda’s built-in native wireless CarPlay menus and connection flow without spoofing your vehicle identity or GPS hardware.</p>
  </a>

  <a class="oc-feature-card" href="services/">
    <div class="oc-feature-head">
      <span class="oc-feature-title">Services &amp; Base optimizations</span>
      <span class="oc-badge">Base: Off · DVD: Off</span>
    </div>
    <p class="oc-feature-desc">Cuts verbose flash logging and stops dead or unused integrations (DAB, TV, Stitcher, Aha, DVD, Pandora, Android Auto, SiriusXM) to lighten startup and free RAM.</p>
  </a>

  <a class="oc-feature-card" href="developer-options/">
    <div class="oc-feature-head">
      <span class="oc-feature-title">Developer options</span>
      <span class="oc-badge">Default: Off</span>
    </div>
    <p class="oc-feature-desc">Optional passwordless UART serial shell and key-based SSH over USB-Ethernet for bench testing and research — off by default.</p>
  </a>

  <a class="oc-feature-card" href="uninstall/">
    <div class="oc-feature-head">
      <span class="oc-feature-title">Built-in Uninstall &amp; recovery</span>
      <span class="oc-badge">Always available</span>
    </div>
    <p class="oc-feature-desc">Removes Open Connect from Mazda Settings or any compatible USB drive, restoring your saved pre-install files and settings cleanly.</p>
  </a>
</div>

## Designed to stay safe and factory-original

- **No permanent system clutter:** Mazda’s original app and service files remain intact on read-only storage; Open Connect stages only the pieces needed for your active choices in RAM.
- **Automatic fallback:** A bounded three-attempt startup guard returns Mazda Connect to its stock startup path if repeated crashes occur — without deleting your settings.
- **Conflict protection:** If another modification changed files Open Connect relies on, install and uninstall stop safely instead of overwriting unknown changes.

Read [How it works](how-it-works.md) for the short architecture overview, or jump straight to [Quick start](usb-installer.md) and [Settings](settings.md).

## Contributing or researching?

- **Build & test:** [Contribute](development.md) · [Wire a bench](bench-setup.md) · [Installer development](installer-development.md)
- **Measurements & RE:** [Performance evidence](performance.md) · [CMU research](cmu/index.md)
