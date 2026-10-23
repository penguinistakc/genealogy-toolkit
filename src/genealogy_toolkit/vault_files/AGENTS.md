# Research Vault: rules for agents

This is a private Research Vault: genealogical research conducted according to the Genealogical Proof Standard. Use the vocabulary defined in the toolkit's [GLOSSARY.md](https://github.com/penguinistakc/genealogy-toolkit/blob/main/GLOSSARY.md): Source, Information, Evidence, Persona, Person, Conclusion, Confidence, Media, Citation, Research Question, Proof Argument. In particular, a scan or recording is Media, not Evidence; and a Persona is not a Person.

## Rules

1. **Every change is a Proposal.** Work on a branch and submit your changes as a pull request. Never commit to `main`; the researcher reviews and merges.
2. **Agents never set or raise Confidence.** You may propose a Conclusion at `Hypothesis` and argue for more in a Proof Argument, but only the researcher changes Confidence.
3. **A Persona records exactly as the Source states.** Copy names, dates, places and relationships verbatim, errors included. Never "correct" a Source; conflicts are resolved in Conclusions. The only permitted edit to an existing Persona is a transcription correction (the Source was misread), recorded in the Persona's `corrections` with what was misread and why.
4. **Every Conclusion traces back to Personas,** and every Persona belongs to a Source with a Citation.
5. **Get every ID from the toolkit.** Start a new Source, Person or Research Question with `gtool new source|person|question "<title, name or question>"`, and get IDs for Personas and Conclusions with `gtool new id persona|conclusion`. Never make IDs up.
6. **Cite Media by ID only,** never by file path. Add a new Media file with `gtool media add <file>`, which prints its ID.
7. **Run `gtool check --since main` before opening a pull request,** and fix every error it reports. It also lists what your Proposal changes (new Personas, Persons and Conclusions, Persona corrections, Confidence changes, and deleted or moved Persons and Conclusions) for the researcher to review.
8. **Every commit is checked.** The Vault's pre-commit hook runs `gtool check` and refuses a commit while the Vault has errors. Never use `--no-verify` (or any other way around the hook); fix the errors instead. If the hook says `gtool` is not installed, install it as it says rather than skipping the check.

## Layout

- `sources/`: one file per Source, with its Personas
- `persons/`: one file per Person, with their Conclusions
- `questions/`: one file per Research Question, with its research log and Proof Argument
- `media/` and `media.yaml`: Media files and the registry mapping Media IDs to them
- `templates/`: starting points for each kind of file
- `.githooks/`: the pre-commit hook that runs `gtool check`, enabled by `gtool vault init`
- `vault.yaml`: the Vault format version, written by `gtool vault init`. Never edit it; if `gtool check` reports the format is newer than gtool understands, stop and tell the researcher to upgrade gtool.
