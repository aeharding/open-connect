# Commander Dial

Adjust how Mazda Connect’s Commander knob scrolls through menus and lists.

<dl class="oc-spec">
  <div>
    <dt>Menu</dt>
    <dd><span class="oc-nav-path" data-walkthrough="commander-dial">Open Connect → Commander Dial</span></dd>
  </div>
  <div>
    <dt>Default</dt>
    <dd><span class="oc-default oc-default--off">Both Off</span></dd>
  </div>
  <div>
    <dt>Impact</dt>
    <dd>Not measured separately</dd>
  </div>
  <div>
    <dt>Applies</dt>
    <dd>Next full startup</dd>
  </div>
</dl>

## Notes

<p>Both options default to <span class="oc-default oc-default--off">Off</span> so fresh installations keep Mazda’s factory Commander Dial behavior. Choices save automatically and apply on the <strong>next full Mazda Connect startup</strong> (use <a href="apply-changes.md">Apply changes</a> to restart right away).</p>

<p>When both options are off, no extra navigation hook code is loaded into Mazda’s UI. Not measured separately in startup or memory benchmarks (see <a href="performance.md">Performance evidence</a>). Bench tests verified setting persistence, UI hook injection and restart on <strong>0.3.0-dev.27</strong> (<strong>74.00.324A NA</strong>); physical Commander knob feel and real-car driving remain unqualified.</p>

## Options

### Wrap-around menus & lists

Wraps Commander Dial focus across the top and bottom ends of standard Mazda Connect menus and lists instead of stopping at the first or last item.

- Applies to standard lists and menus across Mazda Connect.
- Skips disabled items and leaves paginated (lazy-loaded) lists and reorderable lists in Mazda’s normal behavior so pages still load as expected.
- Turning it off restores factory stop-at-ends navigation after restart.

### Faster hold-scroll

Reduces the delay before holding the Commander Dial begins fast-scrolling through long lists, from Mazda’s factory **1.5 seconds** down to **1.0 second**.

- Turning it off restores the factory 1.5-second hold-scroll delay after restart.

[Back to Settings](settings.md)
