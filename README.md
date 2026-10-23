# twp-red-design-build

Odoo 19 Community modules for design / build work in CRM. When a lead comes in, you choose the
line or lines you are designing for, and each line's wizards capture what its design needs. A
heat loss is the first wizard. Design / Build stands on its own: it needs only CRM, and nothing
from Bid / Spec. Radiant Energy Distribution is the first client.

| Module | Status | What it does |
|---|---|---|
| `twp_design_build` | 19.0.1.0.0 | Its own list of design lines, each with a kind that line modules extend. "Designing for" on the lead, one design job per lead and line, building survey records shared by every line, and completion flags that stage checks can read |

Client-specific work, such as Radiant's DRP heat loss, lives in that client's code repo and
depends on `twp_design_build`.

This repo is the master copy. Releases are copied into each client's code repo, which is that
client's addons path on Oduflow.

The plan lives in ThriveWell's tree at `thrivewell/work/design/2026-10-23-design-build-module-plan.md`.
