# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

This repo is early-stage: it currently contains only tooling/scaffolding (Taskfile, pre-commit, mise config) and a README — no application code yet. It's intended to hold documentation and tools for genealogical research.

## Tooling

- [mise-en-place](https://mise.jdx.dev/) pins dev tool versions in `mise.toml` (`task`, `pre-commit`, `node`).
- [go-task](https://taskfile.dev/) (`Taskfile.yml`) is the task runner for all project commands.
- [pre-commit](https://pre-commit.com/) (`.pre-commit-config.yaml`) runs git hooks; its `markdownlint` hook is a `local`/`language: system` hook that shells out to `task lint:markdown`, so hook behavior always matches running the task directly.
- Markdown is linted with `markdownlint-cli2`, invoked via `npx --yes` (no pinned `package.json` dependency). Its config is in `.markdownlint-cli2.jsonc` — default rules, with `MD013` (line length) disabled since content here is prose/docs.

## Setup

Run once after cloning:

```bash
mise install   # installs pinned dev tools (task, pre-commit, node) from mise.toml
task setup     # installs git hooks (pre-commit install)
```

## Common commands

```bash
task lint:markdown        # lint Markdown files
task lint                 # run all linters (currently just lint:markdown)
pre-commit run --all-files  # run all pre-commit hooks against the whole repo
```

The `markdownlint` pre-commit hook only fires on commits that touch `.md` files, and lints the whole repo (not just staged files) when it runs.

## Agent skills

### Issue tracker

Issues are tracked in GitHub Issues on `penguinistakc/genealogy-toolkit`, using the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Uses the five default triage labels (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `GLOSSARY.md` and `docs/adr/` at the repo root, created only when first needed. See `docs/agents/domain.md`.
