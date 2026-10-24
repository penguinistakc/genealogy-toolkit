"""Lays out a Research Vault: folders, templates, and configuration."""

import os
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from importlib.resources import files
from importlib.resources.abc import Traversable
from pathlib import Path

from genealogy_toolkit import media, vault

FOLDERS = ["sources", "persons", "questions", "media"]
HOOKS = ".githooks"
"""Folder in the Vault holding its git hooks; every file in it is executable."""


@dataclass
class InitReport:
    created: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    """Files that already exist with different content, left untouched."""


def init_vault(root: Path) -> InitReport:
    """Create whatever is missing from the Vault skeleton; never overwrite existing files."""
    report = InitReport()
    # Every Vault has had a Media registry since `vault init` existed, so a Vault
    # with one but no format record predates the record and is in the first format.
    # The record is written rather than shipped: it describes this Vault, not the
    # toolkit, so it must never follow the toolkit's own format forward.
    existing = (root / media.REGISTRY).exists()
    root.mkdir(parents=True, exist_ok=True)
    if vault.record_format(root, vault.FIRST_FORMAT if existing else vault.FORMAT):
        report.created.append(vault.FORMAT_FILE)
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
        if relative_path.startswith(f"{HOOKS}/"):
            # importlib.resources yields only content, never file modes.
            target.chmod(0o755)
        report.created.append(relative_path)
    return report


class HookStatus(Enum):
    ENABLED = "enabled"
    """`vault init` just pointed git at the Vault's hooks."""
    ALREADY_ENABLED = "already enabled"
    NOT_A_REPOSITORY = "not a repository"
    """The Vault is not in a git repository, or git is not installed."""
    ELSEWHERE = "elsewhere"
    """`core.hooksPath` already points somewhere else; left untouched."""


@dataclass
class HookReport:
    status: HookStatus
    hooks_path: str = ""
    """The `core.hooksPath` value: the one set, or the one found."""


def enable_hooks(root: Path) -> HookReport:
    """Point git at the Vault's hooks, unless `core.hooksPath` is already set elsewhere.

    The Vault may be a subdirectory of the repository, so the hooks path is
    relative to the top of the working tree, where git runs hooks.
    """
    toplevel = _git(root, "rev-parse", "--show-toplevel")
    if toplevel is None:
        return HookReport(HookStatus.NOT_A_REPOSITORY)
    top = Path(toplevel)
    ours = Path(os.path.relpath(root.resolve() / HOOKS, top)).as_posix()
    current = _git(root, "config", "--get", "core.hooksPath")
    if current:
        if (top / current).resolve() == (top / ours).resolve():
            return HookReport(HookStatus.ALREADY_ENABLED, current)
        return HookReport(HookStatus.ELSEWHERE, current)
    _git(root, "config", "--local", "core.hooksPath", ours)
    return HookReport(HookStatus.ENABLED, ours)


def _git(root: Path, *args: str) -> str | None:
    """Run git in `root`: its output, or None if git is missing or fails."""
    try:
        result = subprocess.run(
            ["git", *args], cwd=root, capture_output=True, text=True, check=False
        )
    except FileNotFoundError:
        return None
    return result.stdout.strip() if result.returncode == 0 else None


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
