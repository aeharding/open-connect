# Edit these docs

The website is built from the Markdown files in **docs/** using
[Zensical](https://zensical.org/). GitHub Pages publishes the reviewed contents of
main at [aeharding.github.io/open-connect](https://aeharding.github.io/open-connect/).

## Preview locally

From the repository root, with Python 3.13:

~~~sh
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[docs]"
.venv/bin/zensical serve
~~~

Open the local URL printed by the command. Before opening a PR, run the same
strict build used by CI:

~~~sh
.venv/bin/zensical build --clean --strict
~~~

Generated output goes to the ignored **site/** directory. Do not commit it.

## Add a page

1. Edit an existing topic or add a Markdown file under docs/.
2. Add new pages to the navigation in **zensical.toml**.
3. Use relative links between documentation pages so they work in the repository
   and on the website. Link to code, issues and root-level documents using their
   GitHub URLs.
4. Build locally, open a PR and obtain the required adversarial review.

Keep one source for each subject. Product direction and the roadmap remain in
the repository's STEERING.md and PLAN.md; link to them rather than copying them.
The lab handoff, bench-state.txt, is deliberately excluded from the website.

## Navigation previews

Wrap an in-car navigation path in inline text with a walkthrough name:

~~~html
<span class="oc-nav-path" data-walkthrough="open-connect">Mazda Settings → System → Open Connect</span>
~~~

The website turns it into a click-only button. Select it to open the Mazda
floating-screen bezel modal with a reviewed Home-first Commander Dial MP4
walkthrough. The screen is a pure `<video muted loop playsinline preload="none">`
with no poster or PNG slideshow fallback. **Play/Pause** controls playback;
**Restart** returns to the beginning and preserves the paused/playing state.
Escape, the close button or the dimmed backdrop closes it and returns focus to
the path. Dragging from inside the modal onto the backdrop does not dismiss it.
Tab stays inside the modal and Zensical shortcuts are suppressed while it is open.
Reduced-motion preferences start playback paused; otherwise it autoplays muted
and loops. Hiding the page pauses playback. Closing pauses and unloads the video,
so there is no video request before a click or background decoding after close.
The path text stays readable in GitHub and with JavaScript disabled.

The trigger-to-video map and route captions are in
**docs/javascripts/nav-preview.js**. Reuse the five reviewed MP4s under
**docs/assets/guide/walkthroughs/**: Open Connect, CarPlay & Android Auto,
Audio sources, Developer options and Mazda Version Information. Per-setting
notes remain below the route caption; each clip shows the shared menu route,
not necessarily an individual setting change. URLs resolve from the script
location, including nested pages and the GitHub Pages subpath.

Mazda’s native Wi-Fi mode and phone-connection directions have no walkthrough
video. Keep those paths as bold text alongside the inline `wireless-mode.png`;
do not add dead triggers or image fallbacks. Keep the
[media provenance and hashes](assets/guide/README.md#commander-dial-mp4-walkthroughs-and-apply-changes-2026-11-25)
intact. The clips retain original timing with prior-frame holds for torn reads;
they are navigation illustrations, not performance timing evidence.

## Keep the direction readable

**Guide is for owners.** Organize it around Quick start, Settings
and Uninstall. Use short numbered steps, the exact on-screen labels, current
direct CMU screenshots and simple diagrams. Explain what to do and what happens
next. Keep the firmware/prerelease limit visible; move build commands, backend
mechanics and qualification evidence to Development or CMU research.
Say “Mazda Connect's main screen,” not “at Home.” Center framed screenshots and
their captions; keep the outer frame compact and the original capture unedited.

**Settings follows the in-car menu.** Match the current on-screen labels and
order. Explain each setting’s effect, default and choices in plain English. Keep
the overview focused on finding Open Connect and saving preferences. Developer
options can stay technical. Keep existing file paths and URLs when reorganizing
navigation. Group bench, performance and research pages under Development.

Write feature introductions for people deciding whether they can use the feature:
what changes, whether it is available, and where to go next. Put commands and
test evidence in developer guides. Describe visible behavior in everyday language,
such as “the screen may briefly go black.” Keep release notes just as approachable.

Lead with the current answer, its evidence and the unresolved question. Keep
overviews short; use a diagram when it explains the decision more clearly.
Label proposals as proposals and match detail to implementation maturity.
A useful experiment or partial improvement is not automatically a delivered
feature. Separate device observations from failures in the capture or runner.

## Setting page template

Give every setting its own Markdown page and sidebar entry, using the exact
in-car label and menu order. Link directly to that page. Keep the old Services
index and its anchors working for existing links.

Use this order on each setting page:

1. The in-car setting name as the H1, followed by a short introduction.
2. A compact `<dl class="oc-spec">` bar with four cells in the same order on every
   page: **Menu**, **Default**, **Impact**, **Applies**. Each cell groups one `<dt>`
   and one `<dd>` in a `<div>`.
3. The unedited native 800×480 screenshot in the existing `.oc-screen` figure.
4. **Notes** below the screenshot for default exceptions, measured startup/RAM
   context, trade-offs, boot implications, restart guidance and evidence limits.
5. Setting-specific choices or steps, then a link back to Settings.

The bar is for tidbits, not paragraphs. Use short defaults such as **Allow**,
**Skip**, **Off**, **Factory**, **On**, **UART/SSH Off** or **—**. Use muted neutral
ink for Off/Factory and subtle green for enabled defaults. Keep Impact on every
page, using compact, evidence-backed wording such as **+21.2 MiB avail proxy**
or **+7.4 MiB avail proxy**. Qualify the Impact label with **(on vs stock)**
or **(off vs stock)** to keep both the metric and comparison visible. Use **Not measured separately**, **Enabled: unmeasured**,
**Restarts to apply**, **Restores pre-install** or **Read-only** where appropriate.
Keep the complete RAM/CPU/startup comparison and limits in Notes below the screenshot.
Use the published dev.20 cohorts and separate n=1 toggle sweep in [Performance evidence](performance.md);
name Stock Show versus installed Skip and Base=0/1 explicitly. Keep Stock comparators in the bar; explain available-RAM proxy values,
CPU percentage points, n=3 versus n=1, and full timing comparisons in Notes.
“Avail” abbreviates the available-RAM proxy, not kernel MemAvailable or raw MemFree.
Use **Next full startup**, **Auto restart**, **Read-only** or **Per setting** for
Applies. Keep the exact memory metric, comparison configuration and outstanding
qualification in Notes.

Keep Menu short: **Open Connect** for top-level settings, **Open Connect →
CarPlay & Android Auto** for phone settings, and **Open Connect → Audio sources**
for audio settings. The overview uses **Settings → System → Open Connect**.
Make the location clickable with `.oc-nav-path` and the existing
`data-walkthrough`; the modal still shows the complete navigation sequence.
Use medium-weight text and dotted text decoration rather than a border underline.

The bar fills the desktop width with four horizontal cells and uses a 2×2 grid
below 40rem. Keep the existing compact bar (about 63px tall on desktop) so the screenshot remains
visible immediately.
Use hairline rules, a subtle surface tint and a 2px Soul Red left edge in both schemes.
Long menu names may wrap on narrow screens; never clip text or overflow the page.
Keep `.oc-default--on` or `.oc-default--off` with `.oc-default` where applicable.

Write clean HTML inside the bar. Only `attr_list` is enabled, so Markdown inside
HTML containers will not be parsed. For example:

~~~html
<dl class="oc-spec">
  <div>
    <dt>Menu</dt>
    <dd><span class="oc-nav-path" data-walkthrough="dvd">Open Connect → Audio sources</span></dd>
  </div>
  <div>
    <dt>Default</dt>
    <dd><span class="oc-default oc-default--off">Off</span></dd>
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
~~~

In Notes, keep owner copy concise and scannable while retaining factual limits:
development prerelease status, pending real-car qualification, links to
[Performance evidence](performance.md) and [Apply changes](apply-changes.md),
and exact conditions for any Navigation delay. Unknown cost is not zero cost,
including SSH when enabled. Define the Linux 3.0.35 available-RAM proxy formula
(`MemFree + Buffers + Cached + SReclaimable − Shmem`, distinct from raw
`MemFree`, `AnonPages` and `Committed_AS`) in [Settings](settings.md) and
[Performance evidence](performance.md) rather than repeating it verbatim on
every setting page, and keep commit SHAs, CI run IDs and PR numbers in
[media provenance](assets/guide/README.md) or developer/research pages instead
of owner-facing captions. Preserve existing anchors when moving content.

Use `<strong>`, `<code>` and `<a>` inside HTML paragraphs. Use documentation
source filenames in links, such as `performance.md` and `settings.md#apply-changes`.
Zensical rewrites these to directory URLs (`../performance/` and
`../settings/#apply-changes`) in generated setting pages. Hardcoding those output
URLs in source adds the page depth twice. Validate both the root and
`/open-connect/` builds and crawl the generated links after changing them.

Use the reviewed `setting-*.png` capture with the corresponding row highlighted
for each setting’s inline figure. The red highlight is Mazda’s native
Commander Dial focus. Show the selected value accurately in captions; captures
may differ from fresh-install defaults. Keep capture provenance accurate. Use
plain prose and lists; avoid hero cards and badges.

Describe dev.20’s <a href="apply-changes.md">Apply changes</a> action above Uninstall:
it is disabled when clean, confirms Restart and applies saved choices with an
automatic Mazda Connect restart. Keep older screenshots labeled with their actual
capture version.

## Dev.20 video and Apply changes provenance

The five Home-first Commander Dial MP4s and three native Apply changes PNGs were
supplied on **November 25, 2026**, from **0.3.0-dev.20** on
**74.00.324A NA/cmu150_NA**, exact reviewed source
`e29b58258c0c9e9f4c4689c7912f634b80008424`,
[CI 45578042314](https://github.com/aeharding/open-connect/actions/runs/45578042314).
The final video files were visually checked by the capture operator for tearing
and private content with Bluetooth off. The Apply changes PNGs show the disabled
row, enabled row and Restart confirmation. They are unedited 800×480 native
captures, inspected offline by the documentation implementer.

Torn video readbacks hold the previous intact native frame at the original
timestamp. The H.264 encodes retain real-time playback and may have capture
stutter; they are walkthroughs only, not performance timing evidence. The
[asset notes](assets/guide/README.md#commander-dial-mp4-walkthroughs-and-apply-changes-2026-11-25)
record every copied SHA-256, duration, size, held-frame count and private evidence
reference. This provenance stays tied to the capture candidate even though later
dev.20 qualification used another source revision.

## Commander Dial capture provenance

The fourteen original November 24 `setting-*.png` images added for
[#137](https://github.com/aeharding/open-connect/issues/137) and
[#143](https://github.com/aeharding/open-connect/issues/143) were supplied on
**November 24, 2026** from **v0.3.0-dev.19**, **74.00.324A NA/cmu150_NA**.
They are unedited native **800×480 `/dev/fb0` BGRA readbacks**, navigated with
Commander Dial events and no touch injection, with Bluetooth disconnected.
Both the documentation implementer and coordinator inspected all fourteen for
personal data, credentials and diagnostic overlays before publication.

The coordinator identified tag commit
[`f478f3b2`](https://github.com/aeharding/open-connect/tree/f478f3b282f6987d86e04c03d83b1a6971d5a3db)
and supplied two archive identities:

- Published GitHub [v0.3.0-dev.19 prerelease](https://github.com/aeharding/open-connect/releases/tag/v0.3.0-dev.19)
  ZIP, as recorded in the release’s `SHA256SUMS`: `c2c09b3123a2145f3582d3ee7f1e692581b1196ab18c5ba60fc198d79716c486`.
- Local coordinator build ZIP: `d4f0feaf4813ef5707d0f2528a0a98b70b571b1def56582b50e35ec463e5048d`.

The coordinator reports that all **50 extracted file members are byte-for-byte
identical** between these archives; the ZIP archive hashes differ.

The Pandora and SiriusXM row captures have since been replaced by the reviewed
post-dev.20 PR #149 images (source `ecddb381`, CI 45597702470, merged main
`291492fa`), with Bluetooth OFF and no DVD row. Their [current provenance](assets/guide/README.md#audio-sources-pr-149-captures-2026-11-25)
is separate; unchanged dev.19 captures retain their attribution.

The [per-file provenance and SHA-256 table](assets/guide/README.md#commander-dial-setting-captures-2026-11-24)
records the copied bytes, shown preferences and private supplied-original paths.
Copying and hash checks were offline; this docs change makes no new live package,
physical-controller or real-car qualification claim. Older ancillary captures
retain their existing identities.

## Write useful reverse-engineering notes

A finding should name the exact firmware and component, explain what was learned,
and distinguish:

- **Observed:** behavior measured on the bench, with the experiment's limits.
- **Source-backed:** conclusions from inspected code or disassembly.
- **Proposed:** a design that still needs implementation or runtime validation.

State what would disprove a hypothesis and what the next useful check is. Keep
the prose concise. Put a new subsystem topic under **docs/cmu/** when it merits
its own page; use the existing findings page for smaller results.

Publish original explanations and sanitized evidence references. Reviewed direct
screenshots and reviewed MP4 walkthroughs of the Open Connect UI are allowed in owner guides; exclude
personal data, credentials and diagnostic overlays. Keep their version/provenance
with the [guide asset notes](assets/guide/README.md). Do not publish raw capture collections, OEM source files,
binaries, private credentials or incompatible comparison code. Mazda's publicly
known default UART login may be documented for onboarding; private credential
files and device-specific secrets remain excluded.
Private evidence paths are provenance, not public downloads. Follow
[THIRD_PARTY.md](https://github.com/aeharding/open-connect/blob/main/THIRD_PARTY.md).

## Publishing

The Documentation workflow builds PRs with strict internal-link and anchor
validation. PRs do not deploy. A successful build on main uploads only the
generated site and deploys it to GitHub Pages; manual dispatch also requires main.

The deployment job alone has Pages and identity-token write permissions. Source
changes still go through review, and generated HTML is never committed to a
separate branch.

Use Mermaid for small architecture and failure-flow diagrams; keep the main
conclusion in text too. [Zensical's diagram guide](https://zensical.org/docs/authoring/diagrams/)
covers the supported syntax and theme behavior.
