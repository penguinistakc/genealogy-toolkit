# Using gtool: a walkthrough

This guide takes you from nothing to a first Proved Conclusion: create a Research Vault, bring in your Ancestry tree and your scans, write up research by hand, let an agent propose research, and review what it proposes. The words in capitals (Source, Persona, Conclusion, Confidence and so on) have exact meanings, defined in [GLOSSARY.md](../GLOSSARY.md).

Every example below is real output from a Vault built from made-up people.

## The idea in one paragraph

Your research lives in a **Research Vault**: a private git repository of plain-text files. A **Source** file records what one document says, person by person, exactly as written; each person in it is a **Persona** ("Ezekiel Fictitious, age 8, in the 1850 census"). A **Person** file holds your **Conclusions** about a real individual, each built from Personas and given a **Confidence** (Hypothesis, Possible, Probable or Proved). A **Research Question** file holds the research log and, once you can make it, the **Proof Argument**. Scans and recordings are **Media**, stored in the Vault and referred to by ID. `gtool` creates the Vault, brings files in, and checks that everything still hangs together.

## Before you start

You need git, [Git LFS](https://git-lfs.com/) (Media files are stored with it), and [uv](https://docs.astral.sh/uv/). Then install a release of `gtool`. The [Releases page](https://github.com/penguinistakc/genealogy-toolkit/releases) lists them, newest first; install one by its tag:

```bash
uv tool install git+https://github.com/penguinistakc/genealogy-toolkit@v0.2.0
gtool --version
```

```text
gtool 0.2.0
```

### Upgrading

Each release says what it means for your Vault in [CHANGELOG.md](../CHANGELOG.md), which is also the text on its Releases page. Before upgrading, read the new release's section, especially "What to do in your Vault". Then install its tag in place of the one you have, and check the Vault:

```bash
uv tool install --force git+https://github.com/penguinistakc/genealogy-toolkit@vX.Y.Z
gtool --version
gtool check .
```

(`uv tool upgrade` doesn't move you to a newer release: it stays on the tag you installed.) If something goes wrong, install the previous tag the same way to go back.

## 1. Create the Vault

Make a git repository for your research, then let `gtool` fill it in:

```bash
git init research-vault
cd research-vault
gtool vault init .
```

```text
created .gitattributes
created .githooks/pre-commit
created AGENTS.md
created CLAUDE.md
created media.yaml
created templates/person.md
created templates/research-question.md
created templates/source.md
created vault.yaml
enabled the pre-commit hook (core.hooksPath = .githooks): every commit now runs gtool check
```

What you get:

| File | What it is |
| --- | --- |
| `sources/`, `persons/`, `questions/` | your research, one file per Source, Person and Research Question (created as you add them) |
| `media/`, `media.yaml` | your scans and recordings, and the registry mapping each Media ID to its file |
| `templates/` | annotated starting points for each kind of file; read them, they document every field |
| `AGENTS.md`, `CLAUDE.md` | the rules any agent working in the Vault must follow |
| `.githooks/pre-commit` | runs `gtool check` on every commit and refuses one that would break the Vault |
| `vault.yaml` | the format version the Vault is written in (`format: 1`); don't edit it |

Running `vault init` again is safe: it never overwrites a file you already have. In a Vault made before `vault.yaml` existed, it adds `vault.yaml` with `format: 1`, which is what `check` assumes for a Vault without one.

The format version is separate from the version of `gtool`, and changes only when existing Vault files would have to change. If your Vault is in a newer format than your `gtool` understands, `check` (and so every commit) refuses it with an error telling you to upgrade `gtool`, rather than misread it.

Put the Vault on a **private** GitHub repository (`gh repo create research-vault --private --source . --push`) if you want agents to propose research as pull requests. This toolkit is public; your Vault must not be.

## 2. Import your Ancestry tree

In Ancestry, export your tree as a GEDCOM file (Trees → your tree → Tree Settings → Export tree). Ancestry downloads it as a zip file holding the GEDCOM (and no Media); import the zip as it is, or the `.ged` inside it:

```bash
gtool import gedcom ~/Downloads/families.zip --vault .
```

```text
imported families.zip as sources/ancestry-tree-export-families-ged-source-6p34ajew.md (source-6p34ajew): 5 Personas, 6 events, 6 relationships (4 parent-child, 2 spouse)
not interpreted, kept verbatim as raw GEDCOM:
  1 × INDI._MILT (on Personas)
  1 × FAM.CHIL._FREL (on the Source)
  1 × SOUR (on the Source)
```

The whole tree becomes **one authored Source**. Each person in it becomes a Persona: a record of what the tree *claims*, not a proved fact. Names, dates and places are kept exactly as Ancestry has them, along with notes, Ancestry's source citations, and anything the importer didn't understand (listed in the report, kept as `raw_gedcom`, never dropped). Here is part of one Persona:

```yaml
- id: persona-966kwba3
  gedcom_id: '@I1@'
  names:
  - Ezekiel Q /Fictitious/
  sex: M
  events:
  - type: birth
    date: abt 1842
    place: Nowhere Township, Imaginary County, Ohio, USA
  - type: marriage
    date: abt 1866
    spouse: persona-43pwxk5s
  relationships:
  - type: spouse
    persona: persona-43pwxk5s
  - type: child
    persona: persona-v3rnrfp2
```

Importing the same export twice does nothing, whether it comes zipped or unzipped. A later export with changes is imported as a new, separate Source, because it is a new statement by the tree.

## 3. Add your scans and recordings

```bash
gtool media add ~/Scans/census-1850.jpg --vault .
```

```text
media-fq6v9rq2
```

The file is copied into `media/` and registered in `media.yaml` with its checksum. The printed **Media ID** is how you refer to it everywhere else. Adding the same file again prints the same ID and stores nothing new. Never refer to a Media file by its path: when Media later moves to other storage, only `media.yaml` changes.

## 4. Record a Source by hand

For each document you've examined (a census page, a death certificate, a Bible record, an interview), write one Source file in `sources/`. Start it with `gtool new`, which copies the Vault's template and gives it a fresh ID:

```bash
gtool new source "1850 U.S. census, Nowhere Township, Imaginary County, Ohio"
```

```text
created sources/1850-u-s-census-nowhere-township-imaginary-county-ohio-source-75zd9cq2.md (source-75zd9cq2)
```

Then fill in the rest. Each Persona needs an ID too; `gtool new id persona` prints one that nothing in the Vault uses yet. A finished Source looks like this:

```yaml
---
id: source-75zd9cq2
title: 1850 U.S. census, Nowhere Township, Imaginary County, Ohio
classification: original
repository: National Archives (image viewed on FamilySearch)
citation: "1850 U.S. census, Imaginary County, Ohio, population schedule, Nowhere Township, p. 12, dwelling 88, family 90, Ezekiel Fictitious household."
media: [media-fq6v9rq2]
personas:
  - id: persona-h69j9tz9
    names: [Ezekiel Fictitious]
    sex: M
    events:
      - type: census
        date: "1850"
        place: Nowhere Township, Imaginary County, Ohio
      - type: birth
        date: abt 1842
        place: Ohio
---

Age 8 in the household. Image is clear.
```

Rules that matter:

- **Write what the document says, errors included.** If the census misspells the name, the Persona misspells it too. Disagreements between Sources are settled in Conclusions, never by "fixing" a Persona.
- **Once committed, a Persona doesn't change**, except to fix your own misreading. Then add an entry to its `corrections` saying what was misread and why. `gtool check --since` flags any other edit.
- **Quote dates and years** that look like numbers (`date: "1850"`). Unquoted, YAML turns them into numbers or calendar dates, and `check` will tell you to quote them.
- **IDs:** always get them from `gtool new` or `gtool new id <kind>` (`source`, `persona`, `person`, `conclusion` or `question`) rather than making them up; `check` reports any duplicate.

## 5. Write Conclusions about a Person

A Person file in `persons/` gathers your Conclusions about one real individual. Start one with `gtool new person "Ezekiel Q. Fictitious"`, and get an ID for each Conclusion with `gtool new id conclusion`. Each Conclusion lists the Personas it relies on. Those may come from several Sources, which is the point: linking "Ezekiel in the 1850 census" and "Ezekiel in the tree" is itself a Conclusion.

```yaml
---
id: person-wadhp7gh
name: Ezekiel Q. Fictitious
conclusions:
  - id: conclusion-4z33zpac
    statement: Ezekiel was born about 1842 in Ohio.
    confidence: Hypothesis
    personas: [persona-h69j9tz9]
---

# Ezekiel Q. Fictitious
```

**Confidence is yours alone.** Start at Hypothesis and raise it as the Evidence supports it. Agents may propose Conclusions at Hypothesis but never set or raise Confidence.

## 6. Ask a Research Question and prove the answer

A Research Question file in `questions/` (start one with `gtool new question "When and where was Ezekiel Q. Fictitious born?"`) holds one focused question, a log of every search (including searches that found nothing), and finally the Proof Argument:

```markdown
---
id: question-rb5rvj8e
question: When and where was Ezekiel Q. Fictitious born?
subjects: [person-wadhp7gh]
status: open
---

# When and where was Ezekiel born?

## Research log

## Proof Argument
```

A Conclusion can only be **Proved** if it names the Research Question that holds its Proof Argument, and that argument has actually been written. `check` enforces this:

```text
error: persons/ezekiel-q-fictitious-person-wadhp7gh.md: Conclusion 'conclusion-4z33zpac' is Proved but names no Research Question holding its Proof Argument
```

```text
error: persons/ezekiel-q-fictitious-person-wadhp7gh.md: Conclusion 'conclusion-4z33zpac' is Proved but its Research Question 'question-rb5rvj8e' has no Proof Argument
```

Once you write the Proof Argument and set `proof: question-rb5rvj8e` on the Conclusion, the check passes.

## 7. Check and commit

```bash
gtool check .
```

No output and exit code 0 mean the Vault is consistent. Otherwise each problem prints as `severity: file: message`. Errors must be fixed; warnings and info lines are for you to read. `check` catches, among other things:

- files it can't read, and fields of the wrong type
- duplicate IDs
- relationships, and a family event's spouse, that point at the Persona itself or at a Persona outside the Source
- Conclusions relying on Personas that don't exist
- unknown Confidence levels and Proved Conclusions without a Proof Argument
- Media that is unregistered, missing, altered, or stored outside the Vault
- a Vault format newer than your `gtool` understands

The most common error is a date or year that looks like a number. Unquoted, YAML reads it as a number, so `check` asks you to quote it:

```text
error: sources/bad.md: field 'personas[0].events[0].date' must be text; put it in quotes to keep it exactly as written, e.g. date: "1850"
```

If your Vault is in a newer format than your `gtool`, `check` stops there rather than misread it:

```text
error: vault.yaml: Vault format 2 is newer than this gtool understands (format 1); upgrade gtool to check this Vault
```

You rarely need to run `check` yourself, because every commit runs `gtool check --staged`, which checks exactly what you staged rather than every file on disk:

```text
pre-commit: gtool check found errors in the staged Vault; fix them, stage the fixes and commit again.
```

Run `gtool check --staged .` yourself to see what a commit would find before you make it.

Don't get around this with `git commit --no-verify`. A broken file in history can't be reviewed later.

## 8. Let an agent research, and review its Proposal

Open Claude Code (or another coding agent) inside the Vault. `CLAUDE.md` points it at `AGENTS.md`, which sets its rules: work on a branch, open a pull request, record Sources exactly as stated, never change Confidence, and run `gtool check --since main` first. Give it one Research Question, for example "Search for Ezekiel Fictitious in the 1860 census and record what you find against question-rb5rvj8e."

The pull request it opens is a **Proposal**. To review it, check out its branch and run:

```bash
gtool check --since main .
```

```text
error: sources/1850-u-s-census-nowhere-township-imaginary-county-ohio-source-75zd9cq2.md: Persona 'persona-h69j9tz9' was edited without a new transcription correction in its 'corrections'; a Persona records exactly what its Source states
warning: persons/ezekiel-q-fictitious-person-wadhp7gh.md: Conclusion 'conclusion-4z33zpac' Confidence changed from Hypothesis to Possible
```

This lists everything the Proposal changed that needs your judgment:

- **errors:** a Persona edited without a correction, deleted, or moved to another Source
- **warnings:** a Confidence change, a deleted or moved Conclusion, a deleted Person, or a file that couldn't be read before the change
- **info:** new Personas, Persons and Conclusions, and corrections made with a stated reason

Errors mean the Proposal must be fixed before you merge. Ask the agent to fix them, or fix them yourself. Warnings and info lines are what to read before you decide. Add `--format json` to any `check` to get the same findings as JSON, for scripts and agents.

## What's not here yet

- Updating a Vault's shipped files (`AGENTS.md`, templates, the hook) when the toolkit changes. `vault init` reports files that differ but never overwrites them.
- The Archive: one command that turns the Vault into an offline website, PDF and GEDCOM for family members.
