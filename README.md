# genealogy-toolkit

Documentation and tools for genealogical research

## Usage

Install the `gtool` command from this repo, then create a Research Vault:

```bash
uv tool install git+https://github.com/penguinistakc/genealogy-toolkit
gtool vault init path/to/research-vault   # in a git repo, also enables a pre-commit hook that runs gtool check --staged
gtool media add scan.jpg --vault path/to/research-vault   # copy in a Media file; prints its ID
gtool import gedcom tree.ged --vault path/to/research-vault   # an Ancestry export becomes one authored Source of Personas
gtool check path/to/research-vault   # validate it; add --format json for agents
gtool check --since main path/to/research-vault   # also review a Proposal: what changed since main
gtool check --staged path/to/research-vault   # check what a commit would hold (the git index), not the working tree
```

## Development

This project uses [mise-en-place](https://mise.jdx.dev/) to manage dev tools (`task`, `pre-commit`, `node`) and [go-task](https://taskfile.dev/) to run project tasks.

Setup, once after cloning:

1. `mise install` — installs the pinned dev tools (`task`, `pre-commit`, `node`, `python`, `uv`) declared in `mise.toml`.
2. `uv sync` — installs the toolkit and its dev dependencies into `.venv`.
3. `task setup` — installs the git hooks (via `pre-commit install`).

Everyday commands:

- `task test` — run the tests.
- `task lint` — run all linters (Markdown and Python).
