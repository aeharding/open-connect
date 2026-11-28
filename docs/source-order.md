# Source order

Reorder Mazda Connect’s Entertainment **Sources** list so phone and media sources appear at the top.

<dl class="oc-spec">
  <div>
    <dt>Menu</dt>
    <dd><span class="oc-nav-path" data-walkthrough="audio-sources">Open Connect → Audio sources</span></dd>
  </div>
  <div>
    <dt>Default</dt>
    <dd><span class="oc-default oc-default--off">Factory</span></dd>
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

<p>Defaults to <span class="oc-default oc-default--off">Factory order</span> (<strong>Factory</strong> in the list) so fresh installations keep Mazda’s standard Sources list. Choices save automatically and apply on the <strong>next full Mazda Connect startup</strong> (use <a href="apply-changes.md">Apply changes</a> to restart right away).</p>

<p>When set to <strong>Factory order</strong>, no reordering hook code is loaded into Mazda’s UI. Not measured separately in startup or memory benchmarks (see <a href="performance.md">Performance evidence</a>). Bench tests verified setting persistence, UI hook injection and restart on <strong>0.3.0-dev.27</strong> (<strong>74.00.324A NA</strong>); real-car driving remains unqualified.</p>

## Options

| Choice | List label | Behavior |
| --- | --- | --- |
| **Factory order** (default) | Factory | Uses Mazda’s standard Entertainment Sources order. |
| **Phone & media first** | Phone first | Moves visible phone and media sources to the top of the Sources list. |

When **Phone & media first** is active, visible sources are promoted in this order:

1. Wireless CarPlay
2. Wired CarPlay
3. Android Auto
4. USB 1
5. USB 2
6. Bluetooth Audio

All remaining visible sources (AM, FM, SiriusXM, CD, AUX, and enabled streaming sources) follow in their original Mazda order. Disabled sources remain hidden.

[Back to Settings](settings.md)
