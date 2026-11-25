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

The website turns it into a button. Select it to open a modal with the reviewed
CMU screens; use the step dots, arrow buttons or Left/Right keys to move between
steps. Manual navigation pauses playback; Play resumes the 2.2-second cycle.
Escape, the close button or the dimmed backdrop closes it and returns focus to
the path. Tab stays inside the modal. Reduced-motion preferences start playback
paused. The text stays readable in GitHub and with JavaScript disabled.

The screen sequences are in **docs/javascripts/nav-preview.js**. Use existing
reviewed captures from **docs/assets/guide/** and keep their provenance intact.
The `version-info` sequence shows the System tab with About visible and the
reviewed Version Information dialog. `wireless-connect`
shows the Wi-Fi prerequisite with directions to the phone-selection screen. Image URLs resolve
from the script location so previews also work on nested pages and under the
GitHub Pages path.

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

1. The in-car setting name as the H1, followed by one sentence describing it.
2. The complete clickable menu path with `.oc-nav-path` and `data-walkthrough`.
3. An unedited native 800×480 screenshot in the existing `.oc-screen` figure.
4. A compact list: **Default**, **Startup & RAM impact**, **Trade-offs & boot implications**,
   **Applies**, **Evidence & limits**.
5. Setting-specific choices or steps, then a link back to Settings.

Use `.oc-default--on` or `.oc-default--off` with `.oc-default` for applicable
fresh-install defaults; keep the text meaningful without color. Begin impact
with **Faster**, **Slightly faster** or **Neutral**, backed by the measured
configuration and named RAM metric. Neutral means no measured gain is
established. Link [Performance evidence](performance.md), name outstanding
qualification, and distinguish older results from the current preview.

Use the reviewed `setting-*.png` capture with the corresponding row highlighted
for each setting’s figure and walkthrough. The red highlight is Mazda’s native
Commander Dial focus. Show the selected value accurately in captions; captures
may differ from fresh-install defaults. Keep capture provenance accurate. Use
plain prose and lists; avoid hero cards and badges.

Describe the current dev.19 restart behavior. Document new controls only after
their implementation merges.

## Commander Dial capture provenance

The fourteen `setting-*.png` images added for
[#137](https://github.com/aeharding/open-connect/issues/137) and
[#143](https://github.com/aeharding/open-connect/issues/143) were supplied on
**November 24, 2026** from **v0.3.0-dev.19**, **74.00.324A NA/cmu150_NA**.
They are unedited native **800×480 `/dev/fb0` BGRA readbacks**, navigated with
Commander Dial events and no touch injection, with Bluetooth disconnected.
Both the documentation implementer and coordinator inspected all fourteen for
personal data, credentials and diagnostic overlays before publication.

The coordinator identified tag commit
[`f478f3b2`](https://github.com/aeharding/open-connect/tree/f478f3b282f6987d86e04c03d83b1a6971d5a3db)
and USB bundle SHA-256
`d4f0feaf4813ef5707d0f2528a0a98b70b571b1def56582b50e35ec463e5048d`.
The [per-file provenance and SHA-256 table](assets/guide/README.md#commander-dial-setting-captures-november-24-2026)
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
screenshots of the current Open Connect UI are allowed in owner guides; exclude
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
