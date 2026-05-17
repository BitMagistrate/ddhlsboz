# ADR-0002 — Monorepo with uv (Python) + pnpm (Node)

* Status: Accepted
* Date: 2026-01-12
* Deciders: CTO, VP Engineering

## Context

We ship both Python services and Node frontends. We need a workspace tool
that handles transitive dependencies, lockfile determinism and Docker layer
caching without forcing a polyglot build system on the team.

## Decision

* **Python**: `uv` workspace, single `pyproject.toml` at repo root, every
  service / package has its own `pyproject.toml`. `uv lock` produces a
  cross-platform lockfile.
* **Node**: `pnpm` workspaces with `pnpm-workspace.yaml`. Frontend apps
  live in `apps/`, shared libraries (if any) in `packages/ts/`.
* No Bazel / Buck / Pants. Make is the universal entry point.

## Consequences

* Single `make bootstrap` installs every dependency in < 90 s on a warm box.
* CI caches `~/.cache/uv` and `~/.local/share/pnpm/store` per branch.
* Docker images are built per-service with multi-stage Dockerfiles that
  use `uv sync --no-dev --frozen --extra <service>`.
