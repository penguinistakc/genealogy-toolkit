# Using gtool: a walkthrough

This guide takes you from nothing to a first Proved Conclusion: create a Research Vault, bring in your Ancestry tree and your scans, write up research by hand, let an agent propose research, and review what it proposes. The words in capitals (Source, Persona, Conclusion, Confidence and so on) have exact meanings, defined in [GLOSSARY.md](../GLOSSARY.md).

Every example below is real output from a Vault built from made-up people.

## The idea in one paragraph

Your research lives in a **Research Vault**: a private git repository of plain-text files. A **Source** file records what one document says, person by person, exactly as written; each person in it is a **Persona** ("Ezekiel Fictitious, age 8, in the 1850 census"). A **Person** file holds your **Conclusions** about a real individual, each built from Personas and given a **Confidence** (Hypothesis, Possible, Probable or Proved). A **Research Question** file holds the research log and, once you can make it, the **Proof Argument**. Scans and recordings are **Media**, stored in the Vault and referred to by ID. `gtool` creates the Vault, brings files in, and checks that everything still hangs together.

## Before you start

You need git, [Git LFS](https://git-lfs.com/) (Media files are stored with it), and [uv](https://docs.astral.sh/uv/). Then install `gtool`:

```bash
uv tool install git+https://github.com/penguinistakc/genealogy-toolkit
gtool --help
```

To pick up a newer version later, run `uv tool upgrade genealogy-toolkit`.

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

Running `vault init` again is safe: it never overwrites a file you already have.

Put the Vault on a **private** GitHub repository (`gh repo create research-vault --private --source . --push`) if you want agents to propose research as pull requests. This toolkit is public; your Vault must not be.

## 2. Import your Ancestry tree

In Ancestry, export your tree as a GEDCOM file (Trees → your tree → Tree Settings → Export tree). Then:

```bash
gtool import gedcom ~/Downloads/families.ged --vault .
```

```text
imported families.ged as sources/ancestry-tree-export-families-ged-source-6p34ajew.md (source-6p34ajew): 5 Personas, 6 events, 6 relationships (4 parent-child, 2 spouse)
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

Importing the same export file twice does nothing. A later export with changes is imported as a new, separate Source, because it is a new statement by the tree.

## 3. Add your scans and recordings

```bash
gtool media add ~/Scans/census-1850.jpg --vault .
```

```text
media-fq6v9rq2
```

The file is copied into `media/` and registered in `media.yaml` with its checksum. The printed **Media ID** is how you refer to it everywhere else. Adding the same file again prints the same ID and stores nothing new. Never refer to a Media file by its path: when Media later moves to other storage, only `media.yaml` changes.

## 4. Record a Source by hand

For each document you've examined (a census page, a death certificate, a Bible record, an interview), write one Source file in `sources/`. Copy `templates/source.md` and fill it in:

```yaml
---
id: source-c1850aaa
title: 1850 U.S. census, Nowhere Township, Imaginary County, Ohio
classification: original
repository: National Archives (image viewed on FamilySearch)
citation: "1850 U.S. census, Imaginary County, Ohio, population schedule, Nowhere Township, p. 12, dwelling 88, family 90, Ezekiel Fictitious household."
media: [media-fq6v9rq2]
personas:
  - id: persona-c1850001
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
- **IDs:** there is no command yet that creates a Source, Person or Research Question with a fresh ID. For now, make one up in the form `source-` plus eight lowercase letters or digits. Any value works as long as no other ID uses it, and `check` reports duplicates.

## 5. Write Conclusions about a Person

A Person file in `persons/` gathers your Conclusions about one real individual. Each Conclusion lists the Personas it relies on. Those may come from several Sources, which is the point: linking "Ezekiel in the 1850 census" and "Ezekiel in the tree" is itself a Conclusion.

```yaml
---
id: person-ezekiel1
name: Ezekiel Q. Fictitious
conclusions:
  - id: conclusion-ezbirth1
    statement: Ezekiel was born about 1842 in Ohio.
    confidence: Hypothesis
    personas: [persona-c1850001]
---

# Ezekiel Q. Fictitious
```

**Confidence is yours alone.** Start at Hypothesis and raise it as the Evidence supports it. Agents may propose Conclusions at Hypothesis but never set or raise Confidence.

## 6. Ask a Research Question and prove the answer

A Research Question file in `questions/` holds one focused question, a log of every search (including searches that found nothing), and finally the Proof Argument:

```markdown
---
id: question-ezbirth1
question: When and where was Ezekiel Q. Fictitious born?
subjects: [person-ezekiel1]
status: open
---

# When and where was Ezekiel born?

## Research log

## Proof Argument
```

A Conclusion can only be **Proved** if it names the Research Question that holds its Proof Argument, and that argument has actually been written. `check` enforces this:

```text
error: persons/ezekiel-fictitious.md: Conclusion 'conclusion-ezbirth1' is Proved but names no Research Question holding its Proof Argument
```

```text
error: persons/ezekiel-fictitious.md: Conclusion 'conclusion-ezbirth1' is Proved but its Research Question 'question-ezbirth1' has no Proof Argument
```

Once you write the Proof Argument and set `proof: question-ezbirth1` on the Conclusion, the check passes.

## 7. Check and commit

```bash
gtool check .
```

No output and exit code 0 mean the Vault is consistent. Otherwise each problem prints as `severity: file: message`. Errors must be fixed; warnings and info lines are for you to read. `check` catches, among other things:

- duplicate IDs
- relationships to Personas outside the Source
- Conclusions relying on Personas that don't exist
- unknown Confidence levels and Proved Conclusions without a Proof Argument
- Media that is unregistered, missing, altered, or stored outside the Vault

You rarely need to run it yourself, because every commit runs it on what you staged:

```text
pre-commit: gtool check found errors in the staged Vault; fix them, stage the fixes and commit again.
```

Don't get around this with `git commit --no-verify`. A broken file in history can't be reviewed later.

## 8. Let an agent research, and review its Proposal

Open Claude Code (or another coding agent) inside the Vault. `CLAUDE.md` points it at `AGENTS.md`, which sets its rules: work on a branch, open a pull request, record Sources exactly as stated, never change Confidence, and run `gtool check --since main` first. Give it one Research Question, for example "Search for Ezekiel Fictitious in the 1860 census and record what you find against question-ezbirth1."

The pull request it opens is a **Proposal**. To review it, check out its branch and run:

```bash
gtool check --since main .
```

```text
error: sources/1850-census-nowhere-township.md: Persona 'persona-c1850001' was edited without a new transcription correction in its 'corrections'; a Persona records exactly what its Source states
warning: persons/ezekiel-fictitious.md: Conclusion 'conclusion-ezbirth1' Confidence changed from Hypothesis to Possible
```

This lists everything the Proposal changed that needs your judgment:

- **errors:** a Persona edited without a correction, deleted, or moved to another Source
- **warnings:** a Confidence change, a deleted or moved Conclusion, a deleted Person, or a file that couldn't be read before the change
- **info:** new Personas, Persons and Conclusions, and corrections made with a stated reason

Errors mean the Proposal must be fixed before you merge. Ask the agent to fix them, or fix them yourself. Warnings and info lines are what to read before you decide. Add `--format json` to any `check` to get the same findings as JSON, for scripts and agents.

## What's not here yet

- A command to create Sources, Persons and Research Questions with fresh IDs (for now, see step 4).
- Updating a Vault's shipped files (`AGENTS.md`, templates, the hook) when the toolkit changes. `vault init` reports files that differ but never overwrites them.
- The Archive: one command that turns the Vault into an offline website, PDF and GEDCOM for family members.
