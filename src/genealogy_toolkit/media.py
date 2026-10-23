"""The Media registry (`media.yaml`): part of the Vault model, and the only code that reads or writes it."""

import hashlib
import mimetypes
import shutil
from dataclasses import dataclass
from datetime import date
from itertools import takewhile
from pathlib import Path
from typing import Any

import yaml

from genealogy_toolkit.ids import new_id

REGISTRY = "media.yaml"
FOLDER = "media"


@dataclass
class MediaItem:
    id: str
    location: str
    """Where the file is stored: a path relative to the Vault root."""
    sha256: str
    """Checksum recorded when the file was added."""
    type: str
    """Media type, e.g. image/jpeg or audio/mpeg."""
    original_filename: str
    added: date
    stored_sha256: str | None = None
    """Checksum of the stored file when the registry was read with `verify`; None if missing."""


class RegistryError(Exception):
    pass


def add_media(root: Path, file: Path) -> tuple[str, bool]:
    """Copy a file into the Vault and register it; returns its Media ID and whether it was new."""
    items = read_registry(root)
    checksum = sha256(file)
    for item in items.values():
        if item.sha256 == checksum:
            return item.id, False
    media_id = new_id("media")
    location = f"{FOLDER}/{media_id}{file.suffix.lower()}"
    (root / FOLDER).mkdir(exist_ok=True)
    shutil.copyfile(file, root / location)
    items[media_id] = MediaItem(
        media_id,
        location,
        checksum,
        mimetypes.guess_type(file.name)[0] or "application/octet-stream",
        file.name,
        date.today(),
    )
    _write_registry(root, items)
    return media_id, True


def read_registry(root: Path, verify: bool = False) -> dict[str, MediaItem]:
    """Every registered Media item, by ID; with `verify`, also checksum each stored file."""
    path = root / REGISTRY
    if not path.is_file():
        raise RegistryError("is missing; run `gtool vault init` to create it")
    try:
        content = yaml.safe_load(path.read_text())
    except yaml.YAMLError as problem:
        raise RegistryError(
            f"is not valid YAML: {problem}".replace("\n", " ")
        ) from None
    if not isinstance(content, dict) or not isinstance(content.get("media"), dict):
        raise RegistryError("must have a 'media' mapping of Media IDs to entries")
    items = {
        str(media_id): _item(str(media_id), entry)
        for media_id, entry in content["media"].items()
    }
    if verify:
        for item in items.values():
            stored = root / item.location
            item.stored_sha256 = sha256(stored) if stored.is_file() else None
    return items


def sha256(file: Path) -> str:
    digest = hashlib.sha256()
    with file.open("rb") as stream:
        while chunk := stream.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def _item(media_id: str, entry: Any) -> MediaItem:
    if not isinstance(entry, dict):
        raise RegistryError(
            f"entry '{media_id}' must be a mapping of field names to values"
        )
    values = {}
    for name in ["location", "sha256", "type", "original_filename"]:
        value = entry.get(name)
        if not isinstance(value, str) or not value:
            raise RegistryError(
                f"entry '{media_id}' field '{name}' is missing or not text"
            )
        values[name] = value
    added = entry.get("added")
    if not isinstance(added, date):
        raise RegistryError(
            f"entry '{media_id}' field 'added' must be a date (YYYY-MM-DD)"
        )
    return MediaItem(media_id, added=added, **values)


def _write_registry(root: Path, items: dict[str, MediaItem]) -> None:
    """Rewrite the registry, keeping the comment block at the top of the file."""
    path = root / REGISTRY
    header = "".join(
        takewhile(
            lambda line: line.startswith("#"),
            path.read_text().splitlines(keepends=True),
        )
    )
    entries = {
        item.id: {
            "location": item.location,
            "sha256": item.sha256,
            "type": item.type,
            "original_filename": item.original_filename,
            "added": item.added,
        }
        for item in items.values()
    }
    body = yaml.safe_dump({"media": entries}, sort_keys=False, allow_unicode=True)
    path.write_text(header + body)
