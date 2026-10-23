# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

This repo is the public toolkit for genealogical research kept in a separate, private plain-text Research Vault (see `GLOSSARY.md` and `docs/adr/`). It is early-stage: the `gtool` command-line tool (a Python package under `src/genealogy_toolkit/`) currently implements `vault init`, `media add` and `check`; the remaining commands are tracked as sub-issues of the spec in issue #4.

- `cli.py` is a thin argparse layer; behavior lives in modules it calls: `scaffold.py` (vault init), `vault.py` (the Vault model, the only code that parses frontmatter), `media.py` (the part of the Vault model that reads and writes the Media registry, `media.yaml`), `ids.py` (random kind-prefixed IDs), `validation.py` (rules over a loaded Vault, each returning `Finding`s).
- Files a new Vault starts with live under `src/genealogy_toolkit/vault_files/` and are copied verbatim by `vault init`, which never overwrites an existing file.
- Tests drive everything through the CLI in-process (`main([...])`) against a temporary directory. Fixtures must be synthetic: this repo is public, so never commit real family data.

## Tooling

- [mise-en-place](https://mise.jdx.dev/) pins dev tool versions in `mise.toml` (`task`, `pre-commit`, `node`, `python`, `uv`).
- [uv](https://docs.astral.sh/uv/) manages Python dependencies (`pyproject.toml`, `uv.lock`); pytest and ruff are dev dependencies.
- [go-task](https://taskfile.dev/) (`Taskfile.yml`) is the task runner for all project commands.
- [pre-commit](https://pre-commit.com/) (`.pre-commit-config.yaml`) runs git hooks; its `markdownlint` hook is a `local`/`language: system` hook that shells out to `task lint:markdown`, so hook behavior always matches running the task directly. The `ruff` hook does the same with `task lint:python`.
- Markdown is linted with `markdownlint-cli2`, invoked via `npx --yes` (no pinned `package.json` dependency). Its config is in `.markdownlint-cli2.jsonc` — default rules, with `MD013` (line length) disabled since content here is prose/docs.

## Setup

Run once after cloning:

```bash
mise install   # installs pinned dev tools (task, pre-commit, node, python, uv) from mise.toml
uv sync        # creates .venv with the toolkit and its dev dependencies
task setup     # installs git hooks (pre-commit install)
```

## Common commands

```bash
task test                 # run the test suite (extra args pass through: task test -- -k init)
task lint:markdown        # lint Markdown files
task lint:python          # ruff check + ruff format --check
task lint                 # run all linters
uv run gtool --help       # run the CLI from the working tree
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
