MAZDA CMU BENCH PROGRESS DASHBOARD
User sync point: https://chatgpt.com/space/page_72594960d3f08191911f2944d96c7eee

index.html is a self-contained offline dashboard. status.json is its sanitized
snapshot data; keep the embedded data identical when refreshing the HTML.
publication.json maps the private remote Page, visualization and download.
Open the Page from another computer under the same ChatGPT account. No Mac Mini
network access is required. Raw logs, credentials and client identifiers stay
on the bench.

Maintenance is part of ongoing work, not a new timer or background schedule.
After a meaningful milestone, refresh the timestamp and scoped status, then
replace the Page visualization and download using fresh read guards. Preserve
the Page URL. Read the Pages write-page skill before cloud edits. Do not claim
a live telemetry feed. Keep old experiment evidence unchanged.
The current HTML uses an optional widget override at load only, so replace its
HTML for a new snapshot rather than assuming live state synchronization.
Preview locally at wide and narrow widths when layout changes. Chrome's native
headless window had a500px minimum despite a420px screenshot request; don't
mistake that cropped capture for CSS overflow. Hosted embed was saved/read back,
but not independently visually previewed. The standalone download remains usable.

Existing profile/source evidence is referenced, not exposed as broken remote
local-file links. HTML has no framework, remote script/CDN or fetch dependency.
