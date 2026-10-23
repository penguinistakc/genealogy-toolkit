"""The Research Vault model: the only code that reads Vault files."""

from collections.abc import Callable
from dataclasses import dataclass, field
from functools import cache
from importlib.resources import files
from pathlib import Path
from typing import Any

import yaml

from genealogy_toolkit import media
from genealogy_toolkit.findings import Finding
from genealogy_toolkit.media import MediaItem


@dataclass
class Relationship:
    type: str
    persona: str
    """ID of another Persona in the same Source."""


@dataclass
class Persona:
    id: str
    relationships: list[Relationship]


@dataclass
class Source:
    file: str
    id: str
    personas: list[Persona]
    media: list[str] = field(default_factory=list)
    """IDs of the Media holding copies of this Source."""


@dataclass
class Conclusion:
    id: str
    confidence: str
    personas: list[str]
    """IDs of the Personas this Conclusion relies on."""
    proof: str
    """ID of the Research Question holding the Proof Argument, or "" if none."""


@dataclass
class Person:
    file: str
    id: str
    conclusions: list[Conclusion]


@dataclass
class ResearchQuestion:
    file: str
    id: str
    proof_argument: str
    """Text of the body's "Proof Argument" section, or "" if there is none."""


@dataclass
class Vault:
    root: Path
    sources: list[Source] = field(default_factory=list)
    persons: list[Person] = field(default_factory=list)
    questions: list[ResearchQuestion] = field(default_factory=list)
    media: dict[str, MediaItem] = field(default_factory=dict)
    """The Media registry, by Media ID."""


class FrontmatterError(Exception):
    pass


class FieldError(Exception):
    def __init__(self, field: str, problem: str) -> None:
        super().__init__(f"field '{field}' {problem}")


def load_vault(root: Path) -> tuple[Vault, list[Finding]]:
    """Load every Source, Person, Research Question and the Media registry, with findings for unreadable files."""
    vault = Vault(root)
    findings: list[Finding] = []
    readers: list[tuple[str, Callable[[str, dict[str, Any], str], Any], list[Any]]] = [
        ("sources", _source, vault.sources),
        ("persons", _person, vault.persons),
        ("questions", _question, vault.questions),
    ]
    for folder, read, loaded in readers:
        for path in sorted((root / folder).rglob("*.md")):
            relative = path.relative_to(root).as_posix()
            try:
                fields, body = read_frontmatter(path.read_text())
                loaded.append(read(relative, fields, body))
            except FrontmatterError as problem:
                findings.append(Finding("error", relative, f"frontmatter {problem}"))
            except FieldError as problem:
                findings.append(Finding("error", relative, str(problem)))
    try:
        vault.media = media.read_registry(root, verify=True)
    except media.RegistryError as problem:
        findings.append(Finding("error", media.REGISTRY, f"Media registry {problem}"))
    return vault, findings


def read_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Split a Markdown file into its YAML frontmatter mapping and its body."""
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip() != "---":
        raise FrontmatterError("is missing: the file must start with a '---' line")
    closing = next(
        (i for i in range(1, len(lines)) if lines[i].rstrip() == "---"), None
    )
    if closing is None:
        raise FrontmatterError("is not closed with a '---' line")
    try:
        fields = yaml.safe_load("".join(lines[1:closing]))
    except yaml.YAMLError as problem:
        raise FrontmatterError(
            f"is not valid YAML: {problem}".replace("\n", " ")
        ) from None
    if not isinstance(fields, dict):
        raise FrontmatterError("must be a mapping of field names to values")
    return fields, "".join(lines[closing + 1 :])


def _source(file: str, fields: dict[str, Any], body: str) -> Source:
    personas = [
        _persona(persona, f"personas[{i}]")
        for i, persona in _mappings(fields, "personas", "")
    ]
    media_ids = fields.get("media") or []
    if not isinstance(media_ids, list) or not all(
        isinstance(m, str) for m in media_ids
    ):
        raise FieldError("media", "must be a list of Media IDs")
    return Source(file, _id(fields, ""), personas, media_ids)


def _persona(fields: dict[str, Any], prefix: str) -> Persona:
    relationships = [
        Relationship(
            _text(relationship, f"{prefix}.relationships[{i}].", "type"),
            _text(relationship, f"{prefix}.relationships[{i}].", "persona"),
        )
        for i, relationship in _mappings(fields, "relationships", f"{prefix}.")
    ]
    return Persona(_id(fields, f"{prefix}."), relationships)


def _person(file: str, fields: dict[str, Any], body: str) -> Person:
    conclusions = [
        _conclusion(conclusion, f"conclusions[{i}].")
        for i, conclusion in _mappings(fields, "conclusions", "")
    ]
    return Person(file, _id(fields, ""), conclusions)


def _conclusion(fields: dict[str, Any], prefix: str) -> Conclusion:
    personas = fields.get("personas") or []
    if not isinstance(personas, list) or not all(isinstance(p, str) for p in personas):
        raise FieldError(f"{prefix}personas", "must be a list of Persona IDs")
    return Conclusion(
        _id(fields, prefix),
        _text(fields, prefix, "confidence"),
        personas,
        _text(fields, prefix, "proof", required=False),
    )


def _question(file: str, fields: dict[str, Any], body: str) -> ResearchQuestion:
    return ResearchQuestion(file, _id(fields, ""), _section(body, "Proof Argument"))


def _id(fields: dict[str, Any], prefix: str) -> str:
    return _text(fields, prefix, "id")


def _text(fields: dict[str, Any], prefix: str, name: str, required: bool = True) -> str:
    value = fields.get(name)
    if value is None or value == "":
        if required:
            raise FieldError(f"{prefix}{name}", "is missing or empty")
        return ""
    if not isinstance(value, str):
        raise FieldError(f"{prefix}{name}", "must be text")
    return value


def _mappings(
    fields: dict[str, Any], name: str, prefix: str
) -> list[tuple[int, dict[str, Any]]]:
    """The entries of an optional list-of-mappings field, with their positions."""
    value = fields.get(name) or []
    if not isinstance(value, list):
        raise FieldError(f"{prefix}{name}", "must be a list")
    for i, entry in enumerate(value):
        if not isinstance(entry, dict):
            raise FieldError(
                f"{prefix}{name}[{i}]", "must be a mapping of field names to values"
            )
    return list(enumerate(value))


@cache
def template_proof_argument() -> str:
    """The placeholder Proof Argument text in the Research Question template."""
    template = files("genealogy_toolkit") / "vault_files/templates/research-question.md"
    _, body = read_frontmatter(template.read_text())
    return _section(body, "Proof Argument")


def _section(body: str, heading: str) -> str:
    """The text under a level-2 heading, up to the next level-2 heading."""
    lines = body.splitlines()
    try:
        start = lines.index(f"## {heading}") + 1
    except ValueError:
        return ""
    end = next(
        (i for i in range(start, len(lines)) if lines[i].startswith("## ")), len(lines)
    )
    return "\n".join(lines[start:end]).strip()
