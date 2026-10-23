"""Reads GEDCOM 5.5.1 files into a tree of records, without interpreting their tags.

Only the line grammar is handled here: `level [@xref@] tag [value]`, with CONC and
CONT lines folded into the value they continue. What the tags mean is up to the
importer.
"""

import re
from dataclasses import dataclass, field

LINE = re.compile(r"(\d+) +(?:(@[^@ ]+@) +)?([A-Za-z0-9_]+)(?: (.*))?")
NEWLINES = re.compile(r"\r\n|\r|\n")


class GedcomError(Exception):
    pass


@dataclass
class Record:
    level: int
    xref: str
    """The record's own identifier, such as "@I1@", or "" if it has none."""
    tag: str
    value: str
    """The line's value exactly as written, with continuation lines folded in."""
    line: int
    children: list[Record] = field(default_factory=list)

    def all(self, tag: str) -> list[Record]:
        return [child for child in self.children if child.tag == tag]

    def first(self, tag: str) -> Record | None:
        return next(iter(self.all(tag)), None)

    def value_of(self, tag: str) -> str:
        """The value of the first child with this tag, or "" if there is none."""
        child = self.first(tag)
        return child.value if child else ""

    def lines(self, alone: bool = False) -> str:
        """This record and everything under it (or alone) written back out as GEDCOM lines.

        Continued values come back as CONT lines; where CONC lines split a value is
        not kept, since it carries no meaning.
        """
        first, *rest = self.value.split("\n")
        own = [
            " ".join(part for part in (str(self.level), self.xref, self.tag) if part)
        ]
        if first:
            own[0] += f" {first}"
        own += [f"{self.level + 1} CONT {line}".rstrip() for line in rest]
        if alone:
            return "\n".join(own)
        return "\n".join(own + [child.lines() for child in self.children])


def parse(data: bytes) -> list[Record]:
    """The level-0 records of a UTF-8 GEDCOM file (with or without a byte order mark)."""
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as problem:
        raise GedcomError(
            f"is not UTF-8 text (unreadable byte at offset {problem.start}); "
            "export it again as UTF-8"
        ) from None
    records: list[Record] = []
    path: list[Record] = []  # the most recent record at each level, from level 0 down
    for number, line in enumerate(NEWLINES.split(text), 1):
        if not line.strip():
            continue
        match = LINE.fullmatch(line.lstrip())
        if match is None:
            raise GedcomError(f"line {number} is not a GEDCOM line: {line!r}")
        level = int(match[1])
        tag, value = match[3], match[4] or ""
        if level > len(path) or (tag in ("CONC", "CONT") and level == 0):
            raise GedcomError(
                f"line {number} has no parent record at level {level - 1}"
            )
        del path[level:]
        if tag == "CONC":
            path[-1].value += value
            continue
        if tag == "CONT":
            path[-1].value += "\n" + value
            continue
        record = Record(level, match[2] or "", tag, value, number)
        (path[-1].children if path else records).append(record)
        path.append(record)
    return records
