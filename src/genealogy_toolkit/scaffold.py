"""Lays out a Research Vault: folders, templates, and configuration."""

from dataclasses import dataclass, field
from importlib.resources import files
from importlib.resources.abc import Traversable
from pathlib import Path

FOLDERS = ["sources", "persons", "questions", "media"]


@dataclass
class InitReport:
    created: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    """Files that already exist with different content, left untouched."""


def init_vault(root: Path) -> InitReport:
    """Create whatever is missing from the Vault skeleton; never overwrite existing files."""
    report = InitReport()
    for folder in FOLDERS:
        (root / folder).mkdir(parents=True, exist_ok=True)
    for relative_path, content in _vault_files(
        files("genealogy_toolkit") / "vault_files"
    ):
        target = root / relative_path
        if target.exists():
            if target.read_text() != content:
                report.skipped.append(relative_path)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        report.created.append(relative_path)
    return report


def _vault_files(directory: Traversable, prefix: str = "") -> list[tuple[str, str]]:
    """Every file shipped in the Vault skeleton, as (path within the Vault, content)."""
    found = []
    for entry in directory.iterdir():
        path = f"{prefix}{entry.name}"
        if entry.is_dir():
            found.extend(_vault_files(entry, f"{path}/"))
        else:
            found.append((path, entry.read_text()))
    return found
