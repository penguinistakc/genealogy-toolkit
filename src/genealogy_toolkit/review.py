"""Change review: what a Proposal changed in a Research Vault since an earlier version.

Severities: "error" for changes a Proposal must not make (a Persona edited without a
new transcription correction, deleted, or moved to another Source); "warning" for
changes the researcher must look at (a Conclusion or Person deleted, a Conclusion
moved to another Person or its Confidence changed, a file that could not be read at
the earlier version); "info" for the shape of the Proposal (new Personas, Persons and
Conclusions, and Persona edits that carry a correction).
"""

from collections.abc import Iterator

from genealogy_toolkit.findings import Finding
from genealogy_toolkit.vault import Conclusion, Person, Persona, Source, Vault


def review(before: Vault, after: Vault, ref: str) -> list[Finding]:
    """Classify the differences between two versions of a Vault, `before` read at `ref`.

    A Source or Person file that could not be read at `ref` has nothing to compare
    against, so it is reported once and its contents are not also listed as new; one
    deleted since `ref` is reported as a deletion that cannot be reviewed.
    """
    present = {source.file for source in after.sources}
    present |= {person.file for person in after.persons}
    unreviewable = [file for file in before.unreadable if file in present]
    findings = [
        Finding(
            "warning",
            file,
            f"could not be read at {ref}; changes to it cannot be reviewed",
        )
        for file in unreviewable
    ]
    findings += [
        Finding(
            "warning",
            file,
            f"could not be read at {ref} and was deleted; its deletion cannot be "
            "reviewed",
        )
        for file in before.unreadable
        if file.startswith(("sources/", "persons/"))
        and file not in present
        and file not in after.unreadable
    ]
    return (
        findings
        + persona_changes(before, after)
        + new_personas(before, after, set(unreviewable))
        + person_changes(before, after, set(unreviewable))
        + conclusion_changes(before, after, set(unreviewable))
    )


def persona_changes(before: Vault, after: Vault) -> list[Finding]:
    """Personas are append-only: an edit must add a transcription correction.

    A Persona is defined by its Source, so one that keeps its ID but now sits in a
    different Source has changed where its Information came from.
    """
    now = dict(_personas(after))
    findings = []
    for persona_id, (source, old) in _personas(before):
        if persona_id not in now:
            findings.append(
                Finding(
                    "error",
                    source.file,
                    f"Persona '{persona_id}' was deleted; a Persona records exactly "
                    "what its Source states and is never removed",
                )
            )
            continue
        new_source, new = now[persona_id]
        new_file = new_source.file
        if new_source.id != source.id:
            findings.append(
                Finding(
                    "error",
                    new_file,
                    f"Persona '{persona_id}' was moved from Source '{source.id}' to "
                    f"Source '{new_source.id}'; a Persona records what its own "
                    "Source states",
                )
            )
        if new.fields == old.fields:
            continue
        added = new.corrections[len(old.corrections) :]
        if added and new.corrections[: len(old.corrections)] == old.corrections:
            findings.append(
                Finding(
                    "info",
                    new_file,
                    f"Persona '{persona_id}' was edited with a transcription "
                    f"correction: {'; '.join(str(c) for c in added)}",
                )
            )
        else:
            findings.append(
                Finding(
                    "error",
                    new_file,
                    f"Persona '{persona_id}' was edited without a new transcription "
                    "correction in its 'corrections'; a Persona records exactly what "
                    "its Source states",
                )
            )
    return findings


def new_personas(before: Vault, after: Vault, unreviewable: set[str]) -> list[Finding]:
    existing = {persona_id for persona_id, _ in _personas(before)}
    return [
        Finding("info", source.file, f"new Persona '{persona_id}'")
        for persona_id, (source, _) in _personas(after)
        if persona_id not in existing and source.file not in unreviewable
    ]


def person_changes(
    before: Vault, after: Vault, unreviewable: set[str]
) -> list[Finding]:
    """New and deleted Persons; a deleted Person stands for all its Conclusions."""
    existing = {person.id for person in before.persons}
    now = {person.id for person in after.persons}
    findings = []
    for person in before.persons:
        if person.id not in now:
            count = len(person.conclusions)
            findings.append(
                Finding(
                    "warning",
                    person.file,
                    f"{_person(person)} was deleted, with its {count} "
                    f"Conclusion{'' if count == 1 else 's'}",
                )
            )
    findings += [
        Finding("info", person.file, f"new {_person(person)}")
        for person in after.persons
        if person.id not in existing and person.file not in unreviewable
    ]
    return findings


def conclusion_changes(
    before: Vault, after: Vault, unreviewable: set[str]
) -> list[Finding]:
    """New, deleted and moved Conclusions, and every Conclusion whose Confidence changed.

    Conclusions are matched by ID across the whole Vault, so one that now sits under
    a different Person was moved, not deleted. A Person is named as it is now, or as it
    was at the earlier version if it was deleted.
    """
    earlier = dict(_conclusions(before))
    now = dict(_conclusions(after))
    persons_now = {person.id: person for person in after.persons}
    findings = []
    for conclusion_id, (person, old) in earlier.items():
        if conclusion_id not in now and person.id in persons_now:
            statement = f': "{old.statement}"' if old.statement else ""
            findings.append(
                Finding(
                    "warning",
                    person.file,
                    f"Conclusion '{conclusion_id}' of {_person(persons_now[person.id])} "
                    f"was deleted{statement} at Confidence {old.confidence}",
                )
            )
    for conclusion_id, (person, conclusion) in now.items():
        file = person.file
        if conclusion_id not in earlier:
            if file in unreviewable:
                continue
            findings.append(
                Finding(
                    "info",
                    file,
                    f"new Conclusion '{conclusion_id}' at Confidence "
                    f"{conclusion.confidence}",
                )
            )
            continue
        old_person, old = earlier[conclusion_id]
        if old_person.id != person.id:
            findings.append(
                Finding(
                    "warning",
                    file,
                    f"Conclusion '{conclusion_id}' was moved from "
                    f"{_person(persons_now.get(old_person.id, old_person))} to "
                    f"{_person(person)}",
                )
            )
        if old.confidence != conclusion.confidence:
            findings.append(
                Finding(
                    "warning",
                    file,
                    f"Conclusion '{conclusion.id}' Confidence changed from "
                    f"{old.confidence} to {conclusion.confidence}",
                )
            )
    return findings


def _person(person: Person) -> str:
    """How a review message names a Person: its ID, and its name when it has one."""
    name = f" ({person.name})" if person.name else ""
    return f"Person '{person.id}'{name}"


def _personas(vault: Vault) -> Iterator[tuple[str, tuple[Source, Persona]]]:
    for source in vault.sources:
        for persona in source.personas:
            yield persona.id, (source, persona)


def _conclusions(vault: Vault) -> Iterator[tuple[str, tuple[Person, Conclusion]]]:
    for person in vault.persons:
        for conclusion in person.conclusions:
            yield conclusion.id, (person, conclusion)
