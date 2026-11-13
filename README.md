# Mazda Open Connect

Open Connect improves Mazda Connect reliability and responsiveness while preserving
the OEM feel. This repository contains original feature experiments, bench tools
and reverse-engineering findings.

**Research and development on a dedicated bench; no end-user USB release yet.**
Current reference: first-generation CMU, North America, firmware 55.00.750B.

- Native startup disclaimer bypass and independent undo have been demonstrated.
  Smoother startup handoff remains under investigation.
- Silent Entertainment testing works without a TAU through Mazda's existing
  audio-manager API. A persistent bench profile is being planned.
- Upgrade scoping targets the latest applicable North American firmware; the
  exact package and supported upgrade sequence are not yet established.

## Development

[Working plan](PLAN.md) · [Steering agreement](STEERING.md) ·
[Contributing](CONTRIBUTING.md) · [Issues](https://github.com/aeharding/open-connect/issues)

Use issues for concrete work and pull requests for coherent changes. The primary
developer owns implementation and bench operation; focused reviewers investigate
specific design questions against actual Mazda code.

[Host/bench instructions](README.txt) explain the existing tools.
[Current handoff](notes/afk-session-status.txt) records changing device state.
Historical experiment profiles are evidence, not reusable live authorization.

## License and source material

Original Open Connect code is **AGPL-3.0-or-later**; see [LICENSE](LICENSE).
See [THIRD_PARTY.md](THIRD_PARTY.md) for third-party provenance and exclusions.

OEM firmware, full extracted sources, credentials and raw captures are excluded.
Some integration tests depend on private exact firmware inputs. Paths under
ignored `runs/` refer to local evidence and will not resolve in a public checkout.
Upstream-derived noncommercial comparison adaptations are retained locally and
are not part of this AGPL distribution.
