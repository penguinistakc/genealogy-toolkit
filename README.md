# genealogy-toolkit

Documentation and tools for genealogical research

## Development

This project uses [mise-en-place](https://mise.jdx.dev/) to manage dev tools (`task`, `pre-commit`, `node`) and [go-task](https://taskfile.dev/) to run project tasks.

Setup, once after cloning:

1. `mise install` — installs the pinned dev tools (`task`, `pre-commit`, `node`) declared in `mise.toml`.
2. `task setup` — installs the git hooks (via `pre-commit install`).

Everyday commands:

- `task lint:markdown` — lint Markdown files.
- `task lint` — run all linters.
