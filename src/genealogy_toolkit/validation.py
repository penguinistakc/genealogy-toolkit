"""Rules a loaded Research Vault must satisfy."""

from collections.abc import Iterator

from genealogy_toolkit.findings import Finding
from genealogy_toolkit.media import REGISTRY
from genealogy_toolkit.vault import Vault, template_proof_argument

CONFIDENCE_LEVELS = ["Proved", "Probable", "Possible", "Hypothesis"]


def validate(vault: Vault) -> list[Finding]:
    return (
        unique_ids(vault)
        + relationships_stay_within_source(vault)
        + conclusions_rely_on_personas(vault)
        + confidence_is_a_known_level(vault)
        + proved_conclusions_have_proof_arguments(vault)
        + sources_refer_to_registered_media(vault)
        + media_files_stay_inside_vault(vault)
        + media_files_are_intact(vault)
    )


def unique_ids(vault: Vault) -> list[Finding]:
    """Every Source, Persona, Person, Conclusion and Research Question has its own ID."""
    first_seen: dict[str, str] = {}
    findings = []
    for file, id in _ids(vault):
        if id in first_seen:
            findings.append(
                Finding(
                    "error", file, f"duplicate ID '{id}' (also in {first_seen[id]})"
                )
            )
        else:
            first_seen[id] = file
    return findings


def _ids(vault: Vault) -> Iterator[tuple[str, str]]:
    for source in vault.sources:
        yield source.file, source.id
        for persona in source.personas:
            yield source.file, persona.id
    for person in vault.persons:
        yield person.file, person.id
        for conclusion in person.conclusions:
            yield person.file, conclusion.id
    for question in vault.questions:
        yield question.file, question.id


def relationships_stay_within_source(vault: Vault) -> list[Finding]:
    """A Persona's relationships point at other Personas in the same Source."""
    findings = []
    for source in vault.sources:
        here = {persona.id for persona in source.personas}
        for persona in source.personas:
            for relationship in persona.relationships:
                if relationship.persona not in here:
                    findings.append(
                        Finding(
                            "error",
                            source.file,
                            f"Persona '{persona.id}' has a relationship to "
                            f"'{relationship.persona}', which is not a Persona in this Source",
                        )
                    )
    return findings


def conclusions_rely_on_personas(vault: Vault) -> list[Finding]:
    """Every Persona a Conclusion relies on exists in some Source."""
    personas = {persona.id for source in vault.sources for persona in source.personas}
    findings = []
    for person in vault.persons:
        for conclusion in person.conclusions:
            for persona in conclusion.personas:
                if persona not in personas:
                    findings.append(
                        Finding(
                            "error",
                            person.file,
                            f"Conclusion '{conclusion.id}' relies on Persona '{persona}', "
                            "which does not exist",
                        )
                    )
    return findings


def confidence_is_a_known_level(vault: Vault) -> list[Finding]:
    """Every Conclusion's Confidence is one of the four levels."""
    return [
        Finding(
            "error",
            person.file,
            f"Conclusion '{conclusion.id}' has Confidence '{conclusion.confidence}'; "
            f"it must be one of {', '.join(CONFIDENCE_LEVELS)}",
        )
        for person in vault.persons
        for conclusion in person.conclusions
        if conclusion.confidence not in CONFIDENCE_LEVELS
    ]


def proved_conclusions_have_proof_arguments(vault: Vault) -> list[Finding]:
    """A Proved Conclusion names a Research Question whose Proof Argument is written."""
    questions = {question.id: question for question in vault.questions}
    findings = []
    for person in vault.persons:
        for conclusion in person.conclusions:
            if conclusion.confidence != "Proved":
                continue
            question = questions.get(conclusion.proof)
            if not conclusion.proof:
                problem = "names no Research Question holding its Proof Argument"
            elif question is None:
                problem = f"its Research Question '{conclusion.proof}' does not exist"
            elif question.proof_argument in ("", template_proof_argument()):
                problem = (
                    f"its Research Question '{conclusion.proof}' has no Proof Argument"
                )
            else:
                continue
            findings.append(
                Finding(
                    "error",
                    person.file,
                    f"Conclusion '{conclusion.id}' is Proved but {problem}",
                )
            )
    return findings


def sources_refer_to_registered_media(vault: Vault) -> list[Finding]:
    """Every Media ID a Source refers to is in the Media registry."""
    return [
        Finding(
            "error",
            source.file,
            f"Source '{source.id}' refers to Media '{media_id}', "
            f"which is not registered in {REGISTRY}",
        )
        for source in vault.sources
        for media_id in source.media
        if media_id not in vault.media
    ]


def media_files_stay_inside_vault(vault: Vault) -> list[Finding]:
    """Every registered Media file is stored inside the Vault, so a clone or an Archive has it."""
    return [
        Finding(
            "error",
            REGISTRY,
            f"Media '{item.id}' file '{item.location}' {item.misplaced}; "
            "Media must be stored inside the Vault",
        )
        for item in vault.media.values()
        if item.misplaced
    ]


def media_files_are_intact(vault: Vault) -> list[Finding]:
    """Every registered Media file exists and still has the checksum recorded when it was added."""
    findings = []
    for item in vault.media.values():
        if item.misplaced:
            continue
        if item.stored_sha256 is None:
            problem = "is missing"
        elif item.stored_sha256 != item.sha256:
            problem = "does not match its recorded SHA-256 checksum"
        else:
            continue
        findings.append(
            Finding(
                "error", REGISTRY, f"Media '{item.id}' file '{item.location}' {problem}"
            )
        )
    return findings
