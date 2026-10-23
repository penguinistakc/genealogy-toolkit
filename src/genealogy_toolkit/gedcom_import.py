"""GEDCOM import: one export file becomes one authored Source of Personas."""

import hashlib
from dataclasses import dataclass
from pathlib import Path

from genealogy_toolkit import gedcom
from genealogy_toolkit.gedcom import Record
from genealogy_toolkit.ids import new_id
from genealogy_toolkit.vault import (
    Event,
    Persona,
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


class ImportFailed(Exception):
    pass


@dataclass
class ImportReport:
    source: Source
    already_imported: bool
    """The export's checksum matched an existing Source, so nothing was written."""

    @property
    def personas(self) -> int:
        return len(self.source.personas)

    @property
    def events(self) -> int:
        return sum(len(persona.events) for persona in self.source.personas)


def import_gedcom(root: Path, export: Path) -> ImportReport:
    """Record a GEDCOM export as a new authored Source, unless it is already in the Vault."""
    if not (root / "sources").is_dir():
        raise ImportFailed(
            f"{root} is not a Research Vault (it has no sources folder); "
            "run `gtool vault init` first"
        )
    try:
        data = export.read_bytes()
    except OSError as problem:
        raise ImportFailed(f"cannot read {export}: {problem.strerror}") from None
    try:
        records = gedcom.parse(data)
    except gedcom.GedcomError as problem:
        raise ImportFailed(f"{export.name} {problem}") from None
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
    title = f"{'Ancestry tree' if from_ancestry else 'GEDCOM'} export ({export.name})"
    exported = header.value_of("DATE") if header else ""
    source = Source(
        source_file(title, source_id),
        source_id,
        [_persona(record, taken) for record in records if record.tag == "INDI"],
        title=title,
        classification="authored",
        repository="Ancestry.com" if from_ancestry else software,
        citation=(
            f'{software or "Unknown software"}, GEDCOM export file "{export.name}"'
            + (f", exported {exported}" if exported else "")
            + "."
        ),
        gedcom_sha256=checksum,
    )
    write_source(
        root,
        source,
        f"Imported by `gtool import gedcom` from {export.name}. This is an authored "
        "Source: each Persona records the tree exactly as the export states it, as "
        "claims still to be proved.\n",
    )
    return ImportReport(source, already_imported=False)


def _software(header: Record | None) -> str:
    """The program that wrote the export, as its header names it; "" if it doesn't."""
    if header is None:
        return ""
    system = header.first("SOUR")
    if system is None:
        return ""
    return system.value_of("NAME") or system.value


def _persona(individual: Record, taken: set[str]) -> Persona:
    """An INDI record, exactly as stated."""
    return Persona(
        _unique_id("persona", taken),
        names=[name.value for name in individual.all("NAME")],
        sex=individual.value_of("SEX"),
        events=[
            _event(record)
            for record in individual.children
            if record.tag in EVENT_TYPES
        ],
        gedcom_id=individual.xref,
    )


def _event(record: Record) -> Event:
    """An individual event or residence; its date and place exactly as written."""
    stated_type = record.value_of("TYPE") if record.tag == "EVEN" else ""
    return Event(
        stated_type or EVENT_TYPES[record.tag],
        record.value_of("DATE"),
        record.value_of("PLAC"),
    )


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
