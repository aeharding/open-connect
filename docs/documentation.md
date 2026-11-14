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

## Write useful reverse-engineering notes

A finding should name the exact firmware and component, explain what was learned,
and distinguish:

- **Observed:** behavior measured on the bench, with the experiment's limits.
- **Source-backed:** conclusions from inspected code or disassembly.
- **Proposed:** a design that still needs implementation or runtime validation.

State what would disprove a hypothesis and what the next useful check is. Keep
the prose concise. Put a new subsystem topic under **docs/cmu/** when it merits
its own page; use the existing findings page for smaller results.

Publish original explanations and sanitized evidence references. Do not add OEM
source files, binaries, credentials, raw captures or incompatible comparison code.
Private evidence paths are provenance, not public downloads. Follow
[THIRD_PARTY.md](https://github.com/aeharding/open-connect/blob/main/THIRD_PARTY.md).

## Publishing

The Documentation workflow builds PRs with strict internal-link and anchor
validation. PRs do not deploy. A successful build on main uploads only the
generated site and deploys it to GitHub Pages; manual dispatch also requires main.

The deployment job alone has Pages and identity-token write permissions. Source
changes still go through review, and generated HTML is never committed to a
separate branch.
