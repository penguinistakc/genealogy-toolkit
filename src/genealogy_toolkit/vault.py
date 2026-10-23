"""The Research Vault model: the only code that reads and writes Vault files."""

import re
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from functools import cache
from importlib.resources import files
from pathlib import Path
from typing import Any, Protocol

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
class Event:
    type: str
    """e.g. birth, marriage, death, residence."""
    date: str = ""
    """As written in the Source, e.g. "abt 1842"; "" if the Source gives none."""
    place: str = ""
    """As written in the Source; "" if the Source gives none."""


@dataclass
class Persona:
    id: str
    relationships: list[Relationship] = field(default_factory=list)
    names: list[str] = field(default_factory=list)
    sex: str = ""
    """As stated; "" if the Source doesn't say."""
    events: list[Event] = field(default_factory=list)
    gedcom_id: str = ""
    """The GEDCOM record identifier (xref) this Persona was imported from, if any."""
    corrections: list[Any] = field(default_factory=list)
    """Transcription corrections: what was misread, and why."""
    fields: dict[str, Any] = field(default_factory=dict)
    """Every field exactly as written, for comparing versions of the Persona."""


@dataclass
class Source:
    file: str
    """Path relative to the Vault root."""
    id: str
    personas: list[Persona]
    media: list[str] = field(default_factory=list)
    """IDs of the Media holding copies of this Source."""
    title: str = ""
    classification: str = ""
    """original, derivative or authored."""
    repository: str = ""
    citation: str = ""
    gedcom_sha256: str = ""
    """SHA-256 of the GEDCOM export this Source was imported from, if any."""


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


SOURCE_TEXT = ["title", "classification", "repository", "citation"]
"""Optional text fields of a Source, in the order they are written."""


class FrontmatterError(Exception):
    pass


class FieldError(Exception):
    def __init__(self, field: str, problem: str) -> None:
        super().__init__(f"field '{field}' {problem}")


class GitError(Exception):
    """The Vault could not be read at a git ref."""


class _VaultFiles(Protocol):
    def markdown_files(self, folder: str) -> list[str]:
        """Paths of the Markdown files under a folder, relative to the Vault root."""
        ...

    def read(self, relative: str) -> str: ...


@dataclass
class _Directory:
    """The Vault's files as they are on disk."""

    root: Path

    def markdown_files(self, folder: str) -> list[str]:
        return sorted(
            path.relative_to(self.root).as_posix()
            for path in (self.root / folder).rglob("*.md")
        )

    def read(self, relative: str) -> str:
        return (self.root / relative).read_text()


@dataclass
class _GitRef:
    """The Vault's files as committed at a git ref, read without checking it out.

    git runs from the Vault root, so paths are relative to it whether the Vault is
    the whole repository or a folder inside one.
    """

    root: Path
    ref: str

    def __post_init__(self) -> None:
        self._git(
            "rev-parse",
            "--verify",
            "--quiet",
            "--end-of-options",
            f"{self.ref}^{{commit}}",
        )

    def markdown_files(self, folder: str) -> list[str]:
        listing = self._git(
            "ls-tree", "-r", "-z", "--name-only", self.ref, "--", folder
        )
        return sorted(name for name in listing.split("\0") if name.endswith(".md"))

    def read(self, relative: str) -> str:
        return self._git("cat-file", "blob", f"{self.ref}:./{relative}")

    def _git(self, *args: str) -> str:
        try:
            result = subprocess.run(
                ["git", *args],
                cwd=self.root,
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError as problem:
            raise GitError(f"cannot run git: {problem}") from None
        if result.returncode != 0:
            detail = result.stderr.strip() or f"'{self.ref}' is not a commit"
            raise GitError(f"cannot read the Vault at '{self.ref}': {detail}")
        return result.stdout


def load_vault(root: Path, ref: str | None = None) -> tuple[Vault, list[Finding]]:
    """Load every Source, Person, Research Question and the Media registry, with findings for unreadable files.

    Given a git ref, loads the Sources, Persons and Research Questions as committed at
    that ref instead of the working tree, leaving the Media registry empty; raises
    GitError if git cannot read the Vault there.
    """
    vault_files: _VaultFiles = _Directory(root) if ref is None else _GitRef(root, ref)
    vault = Vault(root)
    findings: list[Finding] = []
    readers: list[tuple[str, Callable[[str, dict[str, Any], str], Any], list[Any]]] = [
        ("sources", _source, vault.sources),
        ("persons", _person, vault.persons),
        ("questions", _question, vault.questions),
    ]
    for folder, read, loaded in readers:
        for relative in vault_files.markdown_files(folder):
            try:
                fields, body = read_frontmatter(vault_files.read(relative))
                loaded.append(read(relative, fields, body))
            except FrontmatterError as problem:
                findings.append(Finding("error", relative, f"frontmatter {problem}"))
            except FieldError as problem:
                findings.append(Finding("error", relative, str(problem)))
    if ref is None:
        try:
            vault.media = media.read_registry(root, verify=True)
        except media.RegistryError as problem:
            findings.append(
                Finding("error", media.REGISTRY, f"Media registry {problem}")
            )
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
    return Source(
        file,
        _id(fields, ""),
        personas,
        media_ids,
        **{name: _text(fields, "", name, required=False) for name in SOURCE_TEXT},
        gedcom_sha256=_text(fields, "", "gedcom_sha256", required=False),
    )


def write_source(root: Path, source: Source, body: str) -> None:
    """Write a new Source file at `source.file`."""
    fields: dict[str, Any] = {"id": source.id}
    fields |= {name: getattr(source, name) for name in SOURCE_TEXT}
    fields["media"] = source.media
    if source.gedcom_sha256:
        fields["gedcom_sha256"] = source.gedcom_sha256
    fields["personas"] = [_persona_fields(persona) for persona in source.personas]
    frontmatter = yaml.dump(
        fields, Dumper=_Dumper, sort_keys=False, allow_unicode=True, width=1_000_000
    )
    path = root / source.file
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{frontmatter}---\n\n{body}")


class _Dumper(yaml.SafeDumper):
    """Writes multi-line text as a literal block, so it reads as it was written."""


_Dumper.add_representer(
    str,
    lambda dumper, text: dumper.represent_scalar(
        "tag:yaml.org,2002:str", text, style="|" if "\n" in text else None
    ),
)


def source_file(title: str, id: str) -> str:
    """Where a new Source is written: a readable slug of its title, then its ID."""
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60].rstrip("-")
    return f"sources/{slug}-{id}.md" if slug else f"sources/{id}.md"


def _persona_fields(persona: Persona) -> dict[str, Any]:
    """A Persona's frontmatter, leaving out whatever its Source doesn't state."""
    fields: dict[str, Any] = {"id": persona.id}
    if persona.gedcom_id:
        fields["gedcom_id"] = persona.gedcom_id
    fields["names"] = persona.names
    if persona.sex:
        fields["sex"] = persona.sex
    fields["events"] = [
        {name: value for name, value in vars(event).items() if value}
        for event in persona.events
    ]
    if persona.relationships:
        fields["relationships"] = [
            {"type": r.type, "persona": r.persona} for r in persona.relationships
        ]
    return fields


def _persona(fields: dict[str, Any], prefix: str) -> Persona:
    relationships = [
        Relationship(
            _text(relationship, f"{prefix}.relationships[{i}].", "type"),
            _text(relationship, f"{prefix}.relationships[{i}].", "persona"),
        )
        for i, relationship in _mappings(fields, "relationships", f"{prefix}.")
    ]
    corrections = fields.get("corrections") or []
    if not isinstance(corrections, list):
        raise FieldError(f"{prefix}.corrections", "must be a list")
    events = [
        Event(
            _text(event, f"{prefix}.events[{i}].", "type"),
            _text(event, f"{prefix}.events[{i}].", "date", required=False),
            _text(event, f"{prefix}.events[{i}].", "place", required=False),
        )
        for i, event in _mappings(fields, "events", f"{prefix}.")
    ]
    return Persona(
        _id(fields, f"{prefix}."),
        relationships,
        names=_texts(fields, f"{prefix}.", "names", "a list of names"),
        sex=_text(fields, f"{prefix}.", "sex", required=False),
        events=events,
        gedcom_id=_text(fields, f"{prefix}.", "gedcom_id", required=False),
        corrections=corrections,
        fields=fields,
    )


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
        problem = "must be text"
        if isinstance(value, int | float | date) and not isinstance(value, bool):
            # YAML reads unquoted 1850 or 1850-03-04 as a number or date, losing the original.
            problem += (
                "; put it in quotes to keep it exactly as written, "
                f'e.g. {name}: "{value}"'
            )
        raise FieldError(f"{prefix}{name}", problem)
    return value


def _texts(fields: dict[str, Any], prefix: str, name: str, what: str) -> list[str]:
    """An optional list-of-text field."""
    value = fields.get(name) or []
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise FieldError(f"{prefix}{name}", f"must be {what}")
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
