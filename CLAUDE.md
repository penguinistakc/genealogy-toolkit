# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

This repo is the public toolkit for genealogical research kept in a separate, private plain-text Research Vault (see `GLOSSARY.md` and `docs/adr/`). It is early-stage: the `gtool` command-line tool (a Python package under `src/genealogy_toolkit/`) currently implements `vault init`, `media add`, `import gedcom`, `new` and `check`; the remaining commands are tracked as sub-issues of the spec in issue #4.

- `cli.py` is a thin argparse layer; behavior lives in modules it calls: `scaffold.py` (vault init), `vault.py` (the Vault model, the only code that parses or writes frontmatter; `find_root` finds the Vault root by looking up from a folder, as git finds a repository, and every command but `vault init` runs on the root it finds; it reads files from the working tree; for `check --since`, from a git ref via `git ls-tree`/`git cat-file` without checking out, leaving the Media registry out; or, for `check --staged` (which the Vault's pre-commit hook runs), from the git index via `git ls-files`/`git cat-file`, reading `media.yaml` from the index but checksumming Media files in the working tree, since Git LFS stages only pointers), `media.py` (the part of the Vault model that reads and writes the Media registry, `media.yaml`), `ids.py` (random kind-prefixed IDs), `create.py` (`gtool new`: a new Source, Person or Research Question file from the Vault's own template, and fresh IDs unused in the Vault), `gedcom_import.py` (GEDCOM export → one authored Source of Personas) on top of `gedcom.py` (a small purpose-built GEDCOM line parser: no third-party library is trusted with the research), `validation.py` (rules over a loaded Vault, each returning `Finding`s), `review.py` (`check --since`: compares two loaded Vaults and returns `Finding`s; "error" fails the check, "warning" and "info" are for the reviewer).
- Files a new Vault starts with live under `src/genealogy_toolkit/vault_files/` and are copied verbatim by `vault init`, which never overwrites an existing file. Files under `vault_files/.githooks/` are made executable on copy (importlib.resources carries no file modes); when the Vault is in a git repo, `vault init` sets `core.hooksPath` to them (relative to the repo's top level, so a Vault in a subdirectory works) unless it is already set elsewhere.
- Tests drive everything through the CLI in-process (`main([...])`) against a temporary directory. Fixtures must be synthetic: this repo is public, so never commit real family data.

## Tooling

- [mise-en-place](https://mise.jdx.dev/) pins dev tool versions in `mise.toml` (`task`, `pre-commit`, `node`, `python`, `uv`), each to an exact version released at least seven days before it was chosen. `RELEASING.md` ("Bumping a tool pin") says how to bump one.
- [uv](https://docs.astral.sh/uv/) manages Python dependencies (`pyproject.toml`, `uv.lock`); pytest and ruff are dev dependencies.
- [go-task](https://taskfile.dev/) (`Taskfile.yml`) is the task runner for all project commands.
- [pre-commit](https://pre-commit.com/) (`.pre-commit-config.yaml`) runs git hooks; its `markdownlint` hook is a `local`/`language: system` hook that shells out to `task lint:markdown`, so hook behavior always matches running the task directly. The `ruff` hook does the same with `task lint:python`.
- Markdown is linted with `markdownlint-cli2`, invoked via `npx --yes` at the exact version pinned in `Taskfile.yml`'s `lint:markdown` task (there is no `package.json`). Its config is in `.markdownlint-cli2.jsonc` — default rules, with `MD013` (line length) disabled since content here is prose/docs.
- CI is GitHub Actions (`.github/workflows/ci.yml`): on every pull request and push to `main`, on `ubuntu-latest` and `macos-latest`, it installs the `mise.toml` tools with `jdx/mise-action`, then runs `uv sync --locked`, `task lint` and `task test`. Actions are pinned to full commit SHAs (version in a trailing comment) and the workflow has read-only `contents` permission.

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

## Releases

Versions follow `docs/adr/0005-versioning-by-impact-on-the-vault.md`: the public interface is the Vault format, the `check` rules, the command line and the files `vault init` ships; the Python modules are internal.

- Any pull request that changes the public interface adds a line, written for the researcher, under "Unreleased" in `CHANGELOG.md`, in the right group ("Changes to the Vault format", "Changes to `check`", "Command line" or "Fixes"), and under "What to do in your Vault" when an existing Vault needs anything done. Docs-only and test-only changes don't.
- Agents may prepare a release pull request by following `RELEASING.md`, but never push release tags: the researcher tags `vX.Y.Z` after merging.

## Agent skills

### Issue tracker

Issues are tracked in GitHub Issues on `penguinistakc/genealogy-toolkit`, using the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Uses the five default triage labels (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `GLOSSARY.md` and `docs/adr/` at the repo root, created only when first needed. See `docs/agents/domain.md`.
