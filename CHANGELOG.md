# Changelog

What each release of the toolkit means for a Research Vault, newest first. Versions follow [ADR 0005](docs/adr/0005-versioning-by-impact-on-the-vault.md): they measure what an existing Vault or script would have to do, not how much code changed. Words in capitals (Source, Persona, Conclusion, Media and so on) are defined in [GLOSSARY.md](GLOSSARY.md).

Each version has a section with its date, grouped under "Changes to the Vault format", "Changes to `check`", "Command line" and "Fixes" (a group is left out when nothing in it changed), and ends with "What to do in your Vault" when a release needs anything done there. "Unreleased" collects changes as they are merged, so a release only renames it.

## Unreleased

The toolkit has not been released yet, so this section covers everything in it: the first release will be the first Vault-ready version.

### Changes to the Vault format

- A Research Vault is a git repository of plain-text files: one Markdown file with YAML frontmatter per Source (in `sources/`), Person (in `persons/`) and Research Question (in `questions/`).
- A Source records its classification, Repository, Citation and Media, and holds its Personas: names, sex, events (with date, place and, for a family event, the spouse), relationships to other Personas in the same Source, and Transcription Corrections under `corrections`.
- A Person holds Conclusions, each with a statement, a Confidence (Hypothesis, Possible, Probable or Proved), the Personas it relies on and, when Proved, the Research Question holding its Proof Argument (`proof`).
- Media files live in `media/`, stored with Git LFS, and are registered by ID and checksum in `media.yaml`. Everything else refers to Media by ID, never by path.
- The Vault records the format it is written in, in `vault.yaml` (`format: 1`). A Vault without one is format 1.
- Every ID is random and prefixed with its kind (`source-`, `persona-`, `person-`, `conclusion-`, `question-`, `media-`).
- `gtool vault init` ships `AGENTS.md` and `CLAUDE.md` (the rules for any agent working in the Vault), annotated templates for each kind of file, a `.gitattributes` for Git LFS, and a pre-commit hook in `.githooks/`.

### Changes to `check`

- `gtool check` validates the whole Vault. It reports as errors:
  - a file it can't read, or a field with the wrong type (an unquoted date or year gets a hint to put it in quotes);
  - duplicate IDs;
  - a relationship, or a family event's spouse, that points at the Persona itself or at a Persona outside its Source;
  - a Conclusion relying on a Persona that doesn't exist;
  - an unknown Confidence level;
  - a Proved Conclusion that names no Research Question, or whose Research Question has no Proof Argument;
  - Media that is unregistered, missing, altered, or stored outside the Vault.
- `gtool check --since <ref>` also reviews a Proposal against an earlier version, such as `main`, naming Persons in its messages:
  - errors: a Persona edited without a new Transcription Correction, deleted, or moved to another Source;
  - warnings: a Confidence change, a deleted or moved Conclusion, a deleted Person, or a file that couldn't be read at the ref;
  - info: new Personas, Persons and Conclusions, and Transcription Corrections with their stated reason.
- `gtool check --staged` checks the Vault as staged for a commit (the git index) rather than the working tree. The Vault's pre-commit hook runs it on every commit.
- `check` first reads the Vault's format, and refuses a `vault.yaml` that is malformed or names a newer format than the installed toolkit understands, saying to upgrade gtool.
- `check` exits 1 when there is any error, 0 otherwise, and 2 when it can't read the Vault from git.

### Command line

- `gtool vault init <path>` lays out a new Vault. In a git repository it also enables the pre-commit hook. Running it again never overwrites a file; it lists the ones that differ from the toolkit's.
- `gtool media add <file>` copies a scan or recording into the Vault, registers it and prints its Media ID. Adding the same file again prints the same ID.
- `gtool import gedcom <file>` turns a GEDCOM export, such as an Ancestry tree, into one authored Source of Personas, with their events, families, notes and citations. It accepts the `.ged` file or the `.zip` Ancestry downloads it in. Anything it doesn't interpret is kept verbatim as `raw_gedcom` and listed in its report. Importing the same export twice does nothing.
- `gtool new source|person|question "<title>"` starts a file from the Vault's own template with a fresh ID. `gtool new id <kind>` prints an ID nothing in the Vault uses yet.
- `gtool check --format json` prints findings as a list of `{severity, file, message}`, for agents and scripts.
- `gtool --version` prints the installed toolkit's version.

### What to do in your Vault

If you created a Vault from an earlier `main`, run `gtool vault init` on it again: it adds the files it is missing (such as the pre-commit hook and `vault.yaml`) and lists any that differ from this version's, without overwriting them; copy in any changes you want, such as the new lines in `AGENTS.md`. Then run `gtool check` and fix any errors it reports.
