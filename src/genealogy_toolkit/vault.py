"""The Research Vault model: the only code that reads and writes Vault files."""

import json
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
    """What the other Persona is to this one: parent, child or spouse."""
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
    spouse: str = ""
    """For an event of a couple, such as a marriage: ID of the other partner's Persona
    in the same Source; "" if the event is not a couple's or names one partner only."""
    notes: list[str] = field(default_factory=list)
    """Notes the Source makes about this event, verbatim."""
    citations: list[str] = field(default_factory=list)
    """References to where the Source got this event, verbatim."""


@dataclass
class Persona:
    id: str
    relationships: list[Relationship] = field(default_factory=list)
    names: list[str] = field(default_factory=list)
    sex: str = ""
    """As stated; "" if the Source doesn't say."""
    events: list[Event] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    """Notes the Source makes about this person, verbatim."""
    citations: list[str] = field(default_factory=list)
    """References to where the Source got what it says about this person, verbatim,
    such as a GEDCOM source citation's lines."""
    gedcom_id: str = ""
    """The GEDCOM record identifier (xref) this Persona was imported from, if any."""
    raw_gedcom: list[str] = field(default_factory=list)
    """GEDCOM lines the import could not interpret, verbatim, so nothing is lost."""
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
    raw_gedcom: list[str] = field(default_factory=list)
    """GEDCOM lines outside any Persona that the import could not interpret, verbatim."""


@dataclass
class Conclusion:
    id: str
    confidence: str
    personas: list[str]
    """IDs of the Personas this Conclusion relies on."""
    proof: str
    """ID of the Research Question holding the Proof Argument, or "" if none."""
    statement: str = ""
    """What the Conclusion asserts, in the researcher's words; "" if not written."""


@dataclass
class Person:
    file: str
    id: str
    conclusions: list[Conclusion]
    name: str = ""
    """Display name only; identity is established by Conclusions. "" if not given."""


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
    unreadable: list[str] = field(default_factory=list)
    """Files that could not be read, relative to the Vault root."""


SOURCE_TEXT = ["title", "classification", "repository", "citation"]
"""Optional text fields of a Source, in the order they are written."""


class FrontmatterError(Exception):
    pass


class FieldError(Exception):
    def __init__(self, field: str, problem: str) -> None:
        super().__init__(f"field '{field}' {problem}")


class GitError(Exception):
    """The Vault could not be read from git: at a ref, or as staged."""


class _VaultFiles(Protocol):
    def markdown_files(self, folder: str) -> list[str]:
        """Paths of the Markdown files under a folder, relative to the Vault root."""
        ...

    def read(self, relative: str) -> str: ...

    def registry(self) -> dict[str, MediaItem]:
        """The Media registry, with each stored file checksummed."""
        ...


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

    def registry(self) -> dict[str, MediaItem]:
        return media.read_registry(self.root, verify=True)


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

    def registry(self) -> dict[str, MediaItem]:
        # Only the Proposal's side of a review is validated, so the registry at a ref,
        # whose Media files are not on disk to checksum, is left out.
        return {}

    def _git(self, *args: str) -> str:
        return _git(
            self.root, f"at '{self.ref}'", f"'{self.ref}' is not a commit", *args
        )


@dataclass
class _GitIndex:
    """The Vault's files as staged in the git index: exactly what a commit would hold.

    git sets GIT_INDEX_FILE for a pre-commit hook (`git commit <path>` stages into a
    temporary index), and the git run here inherits it, so it reads that index.
    """

    root: Path

    def __post_init__(self) -> None:
        self._git("rev-parse", "--is-inside-work-tree")

    def markdown_files(self, folder: str) -> list[str]:
        listing = self._git("ls-files", "-z", "--cached", "--", folder)
        # A file with merge conflicts is listed once for each conflicting version.
        return sorted({name for name in listing.split("\0") if name.endswith(".md")})

    def read(self, relative: str) -> str:
        return self._git("cat-file", "blob", f":./{relative}")

    def registry(self) -> dict[str, MediaItem]:
        """The staged registry, checksumming each Media file as it is in the working tree.

        Media files are kept in Git LFS, so the index holds only a pointer to each; the
        bytes their checksums were recorded for are the ones on disk.
        """
        if not self._git("ls-files", "-z", "--cached", "--", media.REGISTRY):
            raise media.RegistryError(f"is not staged; run `git add {media.REGISTRY}`")
        return media.read_registry(
            self.root, verify=True, text=self.read(media.REGISTRY)
        )

    def _git(self, *args: str) -> str:
        return _git(self.root, "as staged", "not a git repository", *args)


def _git(root: Path, where: str, fallback: str, *args: str) -> str:
    """Run git from the Vault root, so paths are relative to it; GitError if it fails."""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as problem:
        raise GitError(f"cannot run git: {problem}") from None
    if result.returncode != 0:
        detail = result.stderr.strip() or fallback
        raise GitError(f"cannot read the Vault {where}: {detail}")
    return result.stdout


def load_vault(
    root: Path, ref: str | None = None, staged: bool = False
) -> tuple[Vault, list[Finding]]:
    """Load every Source, Person, Research Question and the Media registry, with findings for unreadable files.

    Given a git ref, loads the Sources, Persons and Research Questions as committed at
    that ref instead of the working tree, leaving the Media registry empty. With
    `staged`, loads them and the Media registry as staged in the git index, still
    checksumming the Media files in the working tree. Raises GitError if git cannot
    read the Vault.
    """
    vault_files: _VaultFiles
    if ref is not None:
        vault_files = _GitRef(root, ref)
    elif staged:
        vault_files = _GitIndex(root)
    else:
        vault_files = _Directory(root)
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
                vault.unreadable.append(relative)
                findings.append(Finding("error", relative, f"frontmatter {problem}"))
            except FieldError as problem:
                vault.unreadable.append(relative)
                findings.append(Finding("error", relative, str(problem)))
    try:
        vault.media = vault_files.registry()
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
    return Source(
        file,
        _id(fields, ""),
        personas,
        media_ids,
        **{name: _text(fields, "", name, required=False) for name in SOURCE_TEXT},
        gedcom_sha256=_text(fields, "", "gedcom_sha256", required=False),
        raw_gedcom=_texts(fields, "", "raw_gedcom", "a list of GEDCOM text"),
    )


def write_source(root: Path, source: Source, body: str) -> None:
    """Write a new Source file at `source.file`."""
    fields: dict[str, Any] = {"id": source.id}
    fields |= {name: getattr(source, name) for name in SOURCE_TEXT}
    fields["media"] = source.media
    if source.gedcom_sha256:
        fields["gedcom_sha256"] = source.gedcom_sha256
    fields["personas"] = [_persona_fields(persona) for persona in source.personas]
    if source.raw_gedcom:
        fields["raw_gedcom"] = source.raw_gedcom
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
    return new_file("sources", title, id)


def fill_template(text: str, fields: dict[str, str]) -> str:
    """A template with some of its empty top-level fields set, keeping its comments."""
    for name, value in fields.items():
        # A JSON string is also a valid double-quoted YAML string.
        line = f"{name}: {json.dumps(value, ensure_ascii=False)}"
        empty = re.compile(rf'^{name}: ""', flags=re.MULTILINE)
        text = empty.sub(line.replace("\\", "\\\\"), text, count=1)
    return text


def new_file(folder: str, label: str, id: str) -> str:
    """Where a new file is written in `folder`: a readable slug of its label, then its ID."""
    slug = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")[:60].rstrip("-")
    return f"{folder}/{slug}-{id}.md" if slug else f"{folder}/{id}.md"


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
    if persona.notes:
        fields["notes"] = persona.notes
    if persona.citations:
        fields["citations"] = persona.citations
    if persona.raw_gedcom:
        fields["raw_gedcom"] = persona.raw_gedcom
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
            _text(event, f"{prefix}.events[{i}].", "spouse", required=False),
            _texts(event, f"{prefix}.events[{i}].", "notes", "a list of notes"),
            _texts(event, f"{prefix}.events[{i}].", "citations", "a list of citations"),
        )
        for i, event in _mappings(fields, "events", f"{prefix}.")
    ]
    return Persona(
        _id(fields, f"{prefix}."),
        relationships,
        names=_texts(fields, f"{prefix}.", "names", "a list of names"),
        sex=_text(fields, f"{prefix}.", "sex", required=False),
        events=events,
        notes=_texts(fields, f"{prefix}.", "notes", "a list of notes"),
        citations=_texts(fields, f"{prefix}.", "citations", "a list of citations"),
        gedcom_id=_text(fields, f"{prefix}.", "gedcom_id", required=False),
        raw_gedcom=_texts(fields, f"{prefix}.", "raw_gedcom", "a list of GEDCOM text"),
        corrections=corrections,
        fields=fields,
    )


def _person(file: str, fields: dict[str, Any], body: str) -> Person:
    conclusions = [
        _conclusion(conclusion, f"conclusions[{i}].")
        for i, conclusion in _mappings(fields, "conclusions", "")
    ]
    name = _text(fields, "", "name", required=False)
    return Person(file, _id(fields, ""), conclusions, name)


def _conclusion(fields: dict[str, Any], prefix: str) -> Conclusion:
    personas = fields.get("personas") or []
    if not isinstance(personas, list) or not all(isinstance(p, str) for p in personas):
        raise FieldError(f"{prefix}personas", "must be a list of Persona IDs")
    return Conclusion(
        _id(fields, prefix),
        _text(fields, prefix, "confidence"),
        personas,
        _text(fields, prefix, "proof", required=False),
        _text(fields, prefix, "statement", required=False),
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
