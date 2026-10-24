"""GEDCOM import: one export file becomes one authored Source of Personas."""

import hashlib
import zipfile
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from genealogy_toolkit import gedcom
from genealogy_toolkit.gedcom import Record
from genealogy_toolkit.ids import new_id
from genealogy_toolkit.vault import (
    Event,
    Persona,
    Relationship,
    Source,
    Vault,
    load_vault,
    source_file,
    write_source,
)

EVENT_TYPES = {
    "BIRT": "birth",
    "CHR": "christening",
    "BAPM": "baptism",
    "BARM": "bar mitzvah",
    "BASM": "bas mitzvah",
    "BLES": "blessing",
    "CHRA": "adult christening",
    "CONF": "confirmation",
    "FCOM": "first communion",
    "ORDN": "ordination",
    "ADOP": "adoption",
    "NATU": "naturalization",
    "EMIG": "emigration",
    "IMMI": "immigration",
    "CENS": "census",
    "RESI": "residence",
    "GRAD": "graduation",
    "RETI": "retirement",
    "PROB": "probate",
    "WILL": "will",
    "DEAT": "death",
    "BURI": "burial",
    "CREM": "cremation",
    "EVEN": "event",
}
"""GEDCOM 5.5.1 individual event tags (plus residence), and the type each records."""

FAMILY_EVENT_TYPES = {
    "ANUL": "annulment",
    "CENS": "census",
    "DIV": "divorce",
    "DIVF": "divorce filed",
    "ENGA": "engagement",
    "MARB": "marriage banns",
    "MARC": "marriage contract",
    "MARR": "marriage",
    "MARL": "marriage license",
    "MARS": "marriage settlement",
    "RESI": "residence",
    "EVEN": "event",
}
"""GEDCOM 5.5.1 family event tags (plus residence), recorded on each of the family's partners."""

INDIVIDUAL_EVENT_TYPES = FAMILY_EVENT_TYPES | EVENT_TYPES
"""Event tags understood directly under an individual: its own events, and family
events (such as a marriage) stated on the individual rather than through a family,
which are recorded with no spouse."""

type Understood = dict[str, Understood] | str
"""What the import interprets under a record: each tag it understands, and what it
understands under that. Everything else is kept as raw GEDCOM."""

VERBATIM = "verbatim"
"""The record and everything under it are kept as written, such as a citation."""

NAME_PART = "name part"
"""Understood when it only restates part of the name it is under, as Ancestry's GIVN
and SURN do."""

EVENT: dict[str, Understood] = {"DATE": {}, "PLAC": {}, "NOTE": {}, "SOUR": VERBATIM}

INDIVIDUAL: dict[str, Understood] = {
    # A source reference under a name is kept as a citation with its name line.
    "NAME": {"GIVN": NAME_PART, "SURN": NAME_PART, "SOUR": VERBATIM},
    "SEX": {},
    "NOTE": {},
    "SOUR": VERBATIM,
    # Links to the FAM records, which are where relationships are read from.
    "FAMC": {},
    "FAMS": {},
    **{tag: EVENT for tag in INDIVIDUAL_EVENT_TYPES},
    "EVEN": EVENT | {"TYPE": {}},
}

FAMILY: dict[str, Understood] = {
    "HUSB": {},
    "WIFE": {},
    "CHIL": {},
    **{tag: EVENT for tag in FAMILY_EVENT_TYPES},
    "EVEN": EVENT | {"TYPE": {}},
}

RECORDS = {"HEAD", "SUBM", "INDI", "FAM", "TRLR"}
"""Level-0 records the import interprets. The header and the submitter (who made the
export) only describe the export file; any other record is kept on the Source as raw
GEDCOM."""


class ImportFailed(Exception):
    pass


@dataclass
class ImportReport:
    source: Source
    already_imported: bool
    """The export's checksum matched an existing Source, so nothing was written."""
    uninterpreted: list[tuple[str, str]] = field(default_factory=list)
    """Each record the import could not interpret, as its tag path (such as
    "INDI._MILT") and where its raw GEDCOM was kept."""

    @property
    def personas(self) -> int:
        return len(self.source.personas)

    @property
    def events(self) -> int:
        """Events, counting a couple's event (recorded on both partners) once."""
        events = [event for persona in self.source.personas for event in persona.events]
        couples = sum(bool(event.spouse) for event in events)
        return len(events) - couples + couples // 2

    @property
    def parent_child(self) -> int:
        """Parent-child pairs; each is recorded on both Personas, as parent and child."""
        return self._count("parent")

    @property
    def spouses(self) -> int:
        """Spouse pairs; each is recorded on both Personas."""
        return self._count("spouse") // 2

    def _count(self, type: str) -> int:
        return sum(
            relationship.type == type
            for persona in self.source.personas
            for relationship in persona.relationships
        )


def import_gedcom(root: Path, export: Path) -> ImportReport:
    """Record a GEDCOM export as a new authored Source, unless it is already in the Vault."""
    if not (root / "sources").is_dir():
        raise ImportFailed(
            f"{root} is not a Research Vault (it has no sources folder); "
            "run `gtool vault init` first"
        )
    name, zipped_in, data = _read_export(export)
    try:
        records = gedcom.parse(data)
    except gedcom.GedcomError as problem:
        raise ImportFailed(f"{name} {problem}") from None
    checksum = hashlib.sha256(data).hexdigest()
    vault, _ = load_vault(root)
    for existing in vault.sources:
        if existing.gedcom_sha256 == checksum:
            return ImportReport(existing, already_imported=True)
    taken = _ids(vault)
    source_id = _unique_id("source", taken)
    header = next((record for record in records if record.tag == "HEAD"), None)
    software = _software(header)
    from_ancestry = "ancestry" in software.lower()
    title = f"{'Ancestry tree' if from_ancestry else 'GEDCOM'} export ({name})"
    exported = header.value_of("DATE") if header else ""
    uninterpreted: list[tuple[str, str]] = []
    personas = [
        _persona(record, taken, uninterpreted)
        for record in records
        if record.tag == "INDI"
    ]
    by_xref = {persona.gedcom_id: persona for persona in personas if persona.gedcom_id}
    raw_gedcom = []
    for record in records:
        if record.tag == "FAM":
            paths = _family(record, by_xref)
            raw_gedcom += _keep(record, paths, uninterpreted, on_source=True)
        elif record.tag not in RECORDS:
            uninterpreted.append((record.tag, "the Source"))
            raw_gedcom.append(record.lines())
    source = Source(
        source_file(title, source_id),
        source_id,
        personas,
        title=title,
        classification="authored",
        repository="Ancestry.com" if from_ancestry else software,
        citation=(
            f'{software or "Unknown software"}, GEDCOM export file "{name}"'
            + (f", exported {exported}" if exported else "")
            + "."
        ),
        gedcom_sha256=checksum,
        raw_gedcom=raw_gedcom,
    )
    write_source(
        root,
        source,
        f"Imported by `gtool import gedcom` from {name}"
        + (f" (in {zipped_in})" if zipped_in else "")
        + ". This is an authored "
        "Source: each Persona records the tree exactly as the export states it, as "
        "claims still to be proved.\n",
    )
    return ImportReport(source, already_imported=False, uninterpreted=uninterpreted)


def _read_export(export: Path) -> tuple[str, str, bytes]:
    """The GEDCOM file's name, the zip it came in ("" if none), and its contents."""
    try:
        if not zipfile.is_zipfile(export):
            return export.name, "", export.read_bytes()
        with zipfile.ZipFile(export) as archive:
            members = [
                member
                for member in archive.infolist()
                if PurePosixPath(member.filename).suffix.lower() == ".ged"
                and not member.filename.startswith("__MACOSX/")
            ]
            if not members:
                raise ImportFailed(f"{export.name} holds no GEDCOM file (.ged)")
            if len(members) > 1:
                names = ", ".join(member.filename for member in members)
                raise ImportFailed(
                    f"{export.name} holds more than one GEDCOM file ({names}); "
                    "unzip it and import each one"
                )
            (member,) = members
            return (
                PurePosixPath(member.filename).name,
                export.name,
                archive.read(member),
            )
    except OSError as problem:
        raise ImportFailed(f"cannot read {export}: {problem.strerror}") from None
    except (zipfile.BadZipFile, RuntimeError) as problem:
        raise ImportFailed(f"cannot read {export.name}: {problem}") from None


def _software(header: Record | None) -> str:
    """The program that wrote the export, as its header names it; "" if it doesn't."""
    if header is None:
        return ""
    system = header.first("SOUR")
    if system is None:
        return ""
    return system.value_of("NAME") or system.value


def _persona(
    individual: Record, taken: set[str], uninterpreted: list[tuple[str, str]]
) -> Persona:
    """An INDI record, exactly as stated."""
    return Persona(
        _unique_id("persona", taken),
        names=[name.value for name in individual.all("NAME")],
        sex=individual.value_of("SEX"),
        events=[
            _event(record, INDIVIDUAL_EVENT_TYPES)
            for record in individual.children
            if record.tag in INDIVIDUAL_EVENT_TYPES
        ],
        notes=[note.value for note in individual.all("NOTE")],
        citations=_citations(individual),
        gedcom_id=individual.xref,
        raw_gedcom=_keep(
            individual, _uninterpreted(individual, INDIVIDUAL), uninterpreted
        ),
    )


def _citations(individual: Record) -> list[str]:
    """An INDI record's source references as GEDCOM lines, in the order written.

    A source reference under a name starts with that name's line, so it is clear which
    name it supports.
    """
    citations = []
    for record in individual.children:
        if record.tag == "SOUR":
            citations.append(record.lines())
        elif record.tag == "NAME":
            citations += [
                f"{record.lines(alone=True)}\n{citation.lines()}"
                for citation in record.all("SOUR")
            ]
    return citations


def _family(family: Record, personas: dict[str, Persona]) -> list[list[Record]]:
    """Record a FAM record's partners as each other's spouses and its children's parents.

    The family's events are recorded on each partner, naming the other partner when
    there are two. Returns the records under the
    family that could not be interpreted, including members that are not individuals
    in the export, and the events of a family with no partners to record them on.
    """
    members = [r for r in family.children if r.tag in ("HUSB", "WIFE", "CHIL")]
    partners = [
        personas[r.value] for r in members if r.tag != "CHIL" and r.value in personas
    ]
    children = [
        personas[r.value] for r in members if r.tag == "CHIL" and r.value in personas
    ]
    events = [r for r in family.children if r.tag in FAMILY_EVENT_TYPES]
    whole = [r for r in members if r.value not in personas] + (
        [] if partners else events
    )
    for persona in partners:
        others = [other for other in partners if other is not persona]
        for other in others:
            persona.relationships.append(Relationship("spouse", other.id))
        for child in children:
            persona.relationships.append(Relationship("child", child.id))
            child.relationships.append(Relationship("parent", persona.id))
        spouse = others[0].id if len(others) == 1 else ""
        persona.events += [
            _event(record, FAMILY_EVENT_TYPES, spouse) for record in events
        ]
    paths = [
        path
        for path in _uninterpreted(family, FAMILY)
        if not any(path[0] is record for record in whole)
    ]
    return sorted(paths + [[record] for record in whole], key=lambda p: p[-1].line)


def _event(record: Record, types: dict[str, str], spouse: str = "") -> Event:
    """An event or residence; its date, place, notes and citations exactly as written."""
    stated_type = record.value_of("TYPE") if record.tag == "EVEN" else ""
    return Event(
        stated_type or types[record.tag],
        record.value_of("DATE"),
        record.value_of("PLAC"),
        spouse,
        [note.value for note in record.all("NOTE")],
        [citation.lines() for citation in record.all("SOUR")],
    )


def _uninterpreted(
    record: Record, understood: dict[str, Understood]
) -> Iterator[list[Record]]:
    """Each record under this one that the import does not interpret, after the
    records between them."""
    for child in record.children:
        rule = understood.get(child.tag)
        if rule == VERBATIM or (rule == NAME_PART and child.value in record.value):
            continue
        if isinstance(rule, dict):
            yield from ([child, *path] for path in _uninterpreted(child, rule))
        else:
            yield [child]


def _keep(
    record: Record,
    paths: Iterable[list[Record]],
    uninterpreted: list[tuple[str, str]],
    on_source: bool = False,
) -> list[str]:
    """Raw GEDCOM for each uninterpreted record under this one, noting it in the report.

    Each starts with the lines of the records it is under, so it keeps its context;
    kept on the Source, that includes this record's own line.
    """
    kept = []
    for path in paths:
        *between, leftover = [record, *path] if on_source else path
        uninterpreted.append(
            (
                ".".join([record.tag] + [r.tag for r in path]),
                "the Source" if on_source else "Personas",
            )
        )
        kept.append(
            "\n".join([r.lines(alone=True) for r in between] + [leftover.lines()])
        )
    return kept


def _ids(vault: Vault) -> set[str]:
    return {source.id for source in vault.sources} | {
        persona.id for source in vault.sources for persona in source.personas
    }


def _unique_id(kind: str, taken: set[str]) -> str:
    """A new ID that nothing else in the Vault (or this import) already uses."""
    while (id := new_id(kind)) in taken:
        pass
    taken.add(id)
    return id
