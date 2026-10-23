"""Change review: what a Proposal changed in a Research Vault since an earlier version.

Severities: "error" for changes a Proposal must not make (a Persona edited without a
new transcription correction, or deleted); "warning" for changes the researcher must
look at (a Conclusion's Confidence changed); "info" for the shape of the Proposal (new
Personas, Persons and Conclusions, and Persona edits that carry a correction).
"""

from collections.abc import Iterator

from genealogy_toolkit.findings import Finding
from genealogy_toolkit.vault import Conclusion, Persona, Vault


def review(before: Vault, after: Vault) -> list[Finding]:
    """Classify the differences between two versions of a Vault."""
    return (
        persona_changes(before, after)
        + new_personas(before, after)
        + new_persons(before, after)
        + conclusion_changes(before, after)
    )


def persona_changes(before: Vault, after: Vault) -> list[Finding]:
    """Personas are append-only: an edit must add a transcription correction."""
    now = dict(_personas(after))
    findings = []
    for persona_id, (file, old) in _personas(before):
        if persona_id not in now:
            findings.append(
                Finding(
                    "error",
                    file,
                    f"Persona '{persona_id}' was deleted; a Persona records exactly "
                    "what its Source states and is never removed",
                )
            )
            continue
        new_file, new = now[persona_id]
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


def new_personas(before: Vault, after: Vault) -> list[Finding]:
    existing = {persona_id for persona_id, _ in _personas(before)}
    return [
        Finding("info", file, f"new Persona '{persona_id}'")
        for persona_id, (file, _) in _personas(after)
        if persona_id not in existing
    ]


def new_persons(before: Vault, after: Vault) -> list[Finding]:
    existing = {person.id for person in before.persons}
    return [
        Finding("info", person.file, f"new Person '{person.id}'")
        for person in after.persons
        if person.id not in existing
    ]


def conclusion_changes(before: Vault, after: Vault) -> list[Finding]:
    """New Conclusions, and every Conclusion whose Confidence changed."""
    earlier = {conclusion.id: conclusion for _, conclusion in _conclusions(before)}
    findings = []
    for file, conclusion in _conclusions(after):
        old = earlier.get(conclusion.id)
        if old is None:
            findings.append(
                Finding(
                    "info",
                    file,
                    f"new Conclusion '{conclusion.id}' at Confidence "
                    f"{conclusion.confidence}",
                )
            )
        elif old.confidence != conclusion.confidence:
            findings.append(
                Finding(
                    "warning",
                    file,
                    f"Conclusion '{conclusion.id}' Confidence changed from "
                    f"{old.confidence} to {conclusion.confidence}",
                )
            )
    return findings


def _personas(vault: Vault) -> Iterator[tuple[str, tuple[str, Persona]]]:
    for source in vault.sources:
        for persona in source.personas:
            yield persona.id, (source.file, persona)


def _conclusions(vault: Vault) -> Iterator[tuple[str, Conclusion]]:
    for person in vault.persons:
        for conclusion in person.conclusions:
            yield person.file, conclusion
