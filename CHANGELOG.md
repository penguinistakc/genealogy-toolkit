# Changelog

What each release of the toolkit means for a Research Vault, newest first. Versions follow [ADR 0005](docs/adr/0005-versioning-by-impact-on-the-vault.md): they measure what an existing Vault or script would have to do, not how much code changed. Words in capitals (Source, Persona, Conclusion, Media and so on) are defined in [GLOSSARY.md](GLOSSARY.md).

Each version has a section with its date, grouped under "Changes to the Vault format", "Changes to `check`", "Command line" and "Fixes" (a group is left out when nothing in it changed), and ends with "What to do in your Vault" when a release needs anything done there. "Unreleased" collects changes as they are merged, so a release only renames it.

## Unreleased

### Changes to the Vault format

### Changes to `check`

- `gtool check` always ends with a summary line, so a clean run no longer prints nothing: it counts the Sources (and their Personas), Persons (and their Conclusions), Research Questions and Media it checked, then says "no problems found" or how many errors, warnings and info lines it found, e.g. `checked 2 Sources (6 Personas), 1 Person (1 Conclusion), 1 Research Question, 1 Media: no problems found`. With `--staged` it counts what is staged, and with `--since` its totals include the review's findings. If the Vault's format can't be read, it says `checked nothing` instead of giving counts. `--format json` is unchanged, and so are exit codes. The pre-commit hook shows the summary too, on every commit.
- `gtool check --since <ref>` no longer reviews a Vault whose format can't be read (its `vault.yaml` is malformed or names a newer format). It used to compare that unread, apparently empty Vault with the ref and report every Persona as deleted, burying the one real error; now it reports only the format error, and the summary says `checked nothing, since the Vault's format can't be read: 1 error, ...`. The same goes for `--since` with `--staged`. A Vault that can be read is reviewed as before.

### Command line

- `gtool import gedcom` interprets more of an Ancestry export instead of keeping it as `raw_gedcom`: a source citation attached to a name goes into the Persona's `citations`, starting with the name line it was attached to; a marriage (or other family event, such as a divorce) recorded on a person rather than through a family becomes an event on that Persona with no `spouse`, and is counted in the report; and the submitter record, which only describes the export, is no longer reported. Source, repository and media records, and links to media, are still kept raw and reported.
- `check`, `media add`, `import gedcom` and `new` find the Vault from any folder inside it, as git finds a repository: the nearest folder at or above the given or current one that holds `vault.yaml` (or `media.yaml`, for a Vault made before `vault.yaml`). Run from `sources/`, `persons/` or deeper, they work on the whole Vault, with file paths still relative to the Vault root. Outside any Vault they say `error: <folder> is not inside a Research Vault` instead of suggesting `vault init`, and `check` exits 2. `vault init` refuses a folder inside an existing Vault, naming that Vault's root.
- `gtool vault update [path]` brings the files `vault init` ships (agent rules, templates, the hook) up to date after an upgrade. It creates any that are missing; for each one that differs it says whether it was edited in this Vault, shows a diff and asks whether to replace it. Only `y` or `yes` replaces a file. At a terminal it also records the checksum of each shipped file that already matches, and says how many. Without a terminal (an agent, a script) it only reports, and there is no flag to answer yes for you.
- `gtool vault init` records each shipped file it writes in `vault.yaml`, and its message for a file that differs now says to run `gtool vault update`. It no longer reports `media.yaml` as differing once Media is registered in it.

### What to do in your Vault

- To get these citations and events from an export you already imported, delete its Source file and import the export again (importing it as it is only reports it as already imported). Do this only if nothing relies on that Source's Personas yet: the new import gives them new IDs.
- After upgrading, run `gtool vault update .` at a terminal, review the diff for `AGENTS.md` and answer `y` to take the new version, then commit the changed files, including `vault.yaml`.

## 0.2.0 - 2026-10-24

The first release, so this section covers everything in the toolkit: it is the first version ready for a Research Vault.

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
