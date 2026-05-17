# Docs

This is the long-form documentation for the RoadPulse monorepo. The
hierarchy matches the team boundary, not the codebase shape:

| Folder           | Owner            | What lives here                                    |
| ---------------- | ---------------- | -------------------------------------------------- |
| `adr/`           | Architecture     | Architectural Decision Records, RFC-style          |
| `runbooks/`      | SRE / on-call    | One runbook per failure mode                       |
| `pitch/`         | Founders / BD    | Investor materials, including the canonical pitch  |
| `data/`          | Data engineering | Data dictionary, schema reference                  |
| `conventions/`   | Platform         | Coding conventions, commit format, linting rules   |

The `pitch/roadpulse_pitch.md` document is the **single source of truth**
for product scope, architecture and financials. Everything else points at
it.

For quickstart, see the top-level [`README.md`](../README.md).
