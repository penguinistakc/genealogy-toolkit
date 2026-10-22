# Research Vault is Markdown with YAML frontmatter, one file per thing

Every Source (with its Personas), Person (with its Conclusions), and Research Question (with its research log and Proof Argument) is a Markdown file whose structured fields live in YAML frontmatter. This keeps the Vault readable by people and agents, parseable by scripts, and cleanly diffable in git, and Proof Arguments are prose anyway. Any faster query layer, such as a SQLite index, is generated from the files and never edited directly.

## Considered Options

- **Pure YAML/JSON data with separate Markdown prose**: easier to parse, but splits each thing across files and is harder to read.
- **SQLite as the store**: fast to query, but opaque to diffs and to review of agent Proposals.
- **GEDCOM X JSON**: a recognised standard, but verbose, hard to write by hand, and poorly supported by tools; GEDCOM stays an export format instead.
