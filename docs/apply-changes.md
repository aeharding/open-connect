# Apply changes

Restart Mazda Connect to activate your saved choices. You don’t need a USB drive or computer.

<dl class="oc-spec">
  <div>
    <dt>Menu</dt>
    <dd><span class="oc-nav-path" data-walkthrough="apply-changes">Open Connect</span></dd>
  </div>
  <div>
    <dt>Default</dt>
    <dd>—</dd>
  </div>
  <div>
    <dt>Impact</dt>
    <dd>Restarts to apply</dd>
  </div>
  <div>
    <dt>Applies</dt>
    <dd>Auto restart</dd>
  </div>
</dl>

<figure class="oc-screen">
  <div class="oc-screen-frame"><img src="assets/guide/setting-apply-changes-enabled.png" alt="Apply changes highlighted in Open Connect, above Uninstall, with saved changes waiting for a restart." width="800" height="480"></div>
  <figcaption>Apply changes is available when saved choices need a restart (dev.20).</figcaption>
</figure>

## Notes

<p>No preference; this action asks for confirmation before restarting.</p>

<p><strong>Restarts to apply your saved choices.</strong> No isolated RAM/CPU/startup improvement is measured for this action. Individual settings have their own effects.</p>

<p>Choices save automatically. You can change several settings before applying them together. <strong>restart needed</strong> means a choice is saved but not active yet.</p>

<p><strong>Apply changes</strong> is disabled when there are no pending changes. The Commander Dial skips the disabled row.</p>

<p>Dev.20 Apply changes has software bench verification on <strong>74.00.324A NA</strong>. Real-car qualification remains pending; <a href="performance.md">Performance evidence</a> records the dev.20 cold ACC-off cohorts separately from this action. <strong>0.3.0-dev.21</strong> is a development prerelease.</p>

## Restart now

1. Save your preferences, then return to the Open Connect menu.
2. Select **Apply changes**, just above **Uninstall**.
3. Confirm **Restart**. Keep the car on until Mazda Connect restarts.

<figure class="oc-screen">
  <div class="oc-screen-frame"><img src="assets/guide/apply-changes-confirm.png" alt="Apply changes? Restart Mazda Connect to apply your saved changes. Cancel and Restart buttons." width="800" height="480" loading="lazy"></div>
  <figcaption>Choose Restart to apply saved changes, or Cancel to keep browsing.</figcaption>
</figure>

**Cancel** leaves your saved choices waiting for the next full Mazda Connect startup. A quick ignition off/on may resume the same session. If a save cannot be confirmed, reopen Open Connect and check the choice before trying again.

<figure class="oc-screen">
  <div class="oc-screen-frame"><img src="assets/guide/setting-apply-changes-disabled.png" alt="Apply changes greyed out because there are no pending changes; the Commander Dial highlights Uninstall below it." width="800" height="480" loading="lazy"></div>
  <figcaption>No pending changes: Apply changes is disabled (dev.20).</figcaption>
</figure>

[Back to Settings](settings.md)
