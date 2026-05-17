# Coding conventions

The shortest possible version: **don't surprise the next reader**.

## Python

* Formatter + linter: `ruff` (configured in root `pyproject.toml`).
* Type checker: `mypy --strict`.
* Docstrings: Google style. Public modules and packages have a module
  docstring describing intent and the *most surprising thing* about them.
* Functions over 60 LOC must be reviewed line-by-line; consider splitting
  them.
* Errors: subclass `roadpulse_core.errors.RoadPulseError`, never raise
  bare `Exception`. Privacy violations always go through
  `roadpulse_privacy.errors.PrivacyViolation`.

## TypeScript / JavaScript

* Formatter + linter: `biome`. Run `pnpm --filter ... format`.
* Type checker: `tsc --noEmit` with `strict: true`.
* No `any`. No `as unknown as Foo`. Use generics or explicit narrowing.
* Components live in `src/pages/` (route-level) or `src/components/`
  (shared). One component per file.

## SQL

* Formatter + linter: `sqlfluff` (postgres dialect).
* Migrations are reversible; we track schema in `infra/postgres/init/`.

## Commits

* Conventional Commits: `feat:`, `fix:`, `perf:`, `chore:`, `docs:`,
  `refactor:`, `test:`.
* PR titles match the leading commit.

## Pre-commit hooks

Configured in `.pre-commit-config.yaml`:

* `ruff` (lint + format)
* `biome` (lint + format)
* `sqlfluff` (lint)
* `gitleaks` (secret scan)
* `buf` (protobuf lint)
* `pii-token-check` (custom regex hook for VN-shaped phone + plate)

## Forbidden

* `any`, `Any`, `getattr`, `setattr`, `__import__` outside of
  reflection-heavy infra code.
* `git push --force` on main / master.
* Committing files larger than 1 MiB without LFS.
* Committing `.env` files with real credentials.
