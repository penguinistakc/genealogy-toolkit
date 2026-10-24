# genealogy-toolkit

Documentation and tools for genealogical research

## Usage

New here? Read the [walkthrough](docs/guide.md): it goes from an empty folder to a first Proved Conclusion.

Install the `gtool` command from this repo, then create a Research Vault:

```bash
uv tool install git+https://github.com/penguinistakc/genealogy-toolkit@v0.2.0   # a release; see the Releases page for the latest
gtool vault init path/to/research-vault   # in a git repo, also enables a pre-commit hook that runs gtool check --staged
gtool media add scan.jpg --vault path/to/research-vault   # copy in a Media file; prints its ID
gtool import gedcom tree.zip --vault path/to/research-vault   # an Ancestry export (.ged, or the .zip it downloads as) becomes one authored Source of Personas
gtool new source "1850 census, Ross County, Ohio" --vault path/to/research-vault   # also: new person, new question; prints the file and its ID
gtool new id persona --vault path/to/research-vault   # a fresh unused ID (persona, conclusion, ...) to paste into a file
gtool check path/to/research-vault   # validate it; add --format json for agents
gtool check --since main path/to/research-vault   # also review a Proposal: what changed since main
gtool check --staged path/to/research-vault   # check what a commit would hold (the git index), not the working tree
gtool --version   # which toolkit version is checking your Vault
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
