"""Command-line entry point: `gtool <command> ...`."""

import argparse
import dataclasses
import json
import os
import shlex
import shutil
import sys
from collections import Counter
from collections.abc import Sequence
from importlib.metadata import version
from pathlib import Path

from genealogy_toolkit import (
    create,
    gedcom_import,
    media,
    review,
    scaffold,
    validation,
)
from genealogy_toolkit.findings import Finding
from genealogy_toolkit.vault import GitError, Vault, find_root, load_vault


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="gtool")
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {version('genealogy-toolkit')}",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    vault = commands.add_parser("vault", help="manage a Research Vault")
    vault_commands = vault.add_subparsers(dest="vault_command", required=True)
    init = vault_commands.add_parser("init", help="lay out a new Research Vault")
    init.add_argument("path", type=Path, help="directory to create the Vault in")

    media_parser = commands.add_parser("media", help="manage Media files")
    media_commands = media_parser.add_subparsers(dest="media_command", required=True)
    add = media_commands.add_parser(
        "add", help="copy a file into the Vault as Media and print its ID"
    )
    add.add_argument("file", type=Path, help="image, PDF, audio or video file to add")
    add.add_argument(
        "--vault",
        type=Path,
        default=Path("."),
        help="Vault directory (default: .)",
    )

    check = commands.add_parser("check", help="validate a Research Vault")
    check.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="output format; json is a list of {severity, file, message} (default: text)",
    )
    check.add_argument(
        "--since",
        metavar="REF",
        help="also review a Proposal: report what changed since this git ref",
    )
    check.add_argument(
        "--staged",
        action="store_true",
        help="check the Vault as staged in the git index, i.e. what a commit would "
        "hold, instead of the working tree; Media files are checksummed on disk",
    )
    check.add_argument(
        "path",
        type=Path,
        nargs="?",
        default=Path("."),
        help="Vault directory (default: .)",
    )

    import_ = commands.add_parser("import", help="bring outside material into a Vault")
    import_commands = import_.add_subparsers(dest="import_command", required=True)
    import_gedcom = import_commands.add_parser(
        "gedcom", help="record a GEDCOM export as one authored Source of Personas"
    )
    import_gedcom.add_argument(
        "file", type=Path, help="the GEDCOM export: a .ged file, or a zip holding one"
    )
    import_gedcom.add_argument(
        "--vault",
        type=Path,
        default=Path("."),
        help="Vault directory (default: .)",
    )

    new = commands.add_parser(
        "new", help="start a new Source, Person or Research Question file"
    )
    new_commands = new.add_subparsers(dest="new_command", required=True)
    for kind, label, description in [
        (
            "source",
            "title",
            "what the Source is, e.g. '1850 census, Ross County, Ohio'",
        ),
        ("person", "name", "the Person's display name"),
        ("question", "question", "one focused question, e.g. 'When was John born?'"),
    ]:
        new_kind = new_commands.add_parser(
            kind, help=f"write a new {kind} file from the Vault's template"
        )
        new_kind.add_argument("label", metavar=label, help=description)
        new_kind.add_argument(
            "--vault",
            type=Path,
            default=Path("."),
            help="Vault directory (default: .)",
        )

    new_id = new_commands.add_parser(
        "id", help="print a fresh ID, unused in the Vault, to paste into a file"
    )
    new_id.add_argument("kind", choices=create.ID_KINDS, help="what the ID is for")
    new_id.add_argument(
        "--vault",
        type=Path,
        default=Path("."),
        help="Vault directory (default: .)",
    )

    args = parser.parse_args(argv)
    if args.command == "vault":
        return _vault_init(args.path)
    root = _vault_root(args.path if args.command == "check" else args.vault)
    if root is None:
        # check exits 1 only for errors in a Vault it has read.
        return 2 if args.command == "check" else 1
    if args.command == "new":
        return _new(root, args.new_command, args)
    if args.command == "check":
        return _check(root, args.format, args.since, args.staged)
    if args.command == "media":
        return _media_add(args.file, root)
    return _import_gedcom(root, args.file)


def _vault_root(folder: Path) -> Path | None:
    """The root of the Vault holding `folder`, found as git finds a repository; None
    after saying there is none."""
    if not folder.is_dir():
        print(f"error: {folder}: no such folder", file=sys.stderr)
        return None
    root = find_root(folder)
    if root is None:
        print(
            f"error: {folder.absolute()} is not inside a Research Vault",
            file=sys.stderr,
        )
    return root


def _check(root: Path, output_format: str, since: str | None, staged: bool) -> int:
    try:
        vault, findings = load_vault(root, staged=staged)
        findings += validation.validate(vault)
        if since is not None:
            before, _ = load_vault(root, since)
            findings += review.review(before, vault, since)
    except GitError as problem:
        print(f"gtool: error: {problem}", file=sys.stderr)
        return 2
    if output_format == "json":
        print(
            json.dumps([dataclasses.asdict(finding) for finding in findings], indent=2)
        )
    else:
        for finding in findings:
            print(f"{finding.severity}: {finding.file}: {finding.message}")
        print(_summary(vault, findings))
    return 1 if any(f.severity == "error" for f in findings) else 0


def _summary(vault: Vault, findings: list[Finding]) -> str:
    """One line saying what `check` read and what it found."""
    personas = sum(len(source.personas) for source in vault.sources)
    conclusions = sum(len(person.conclusions) for person in vault.persons)
    if not vault.format_read:
        # Counts of nothing would claim the Vault is empty: it was not read at all.
        checked = "checked nothing, since the Vault's format can't be read"
    else:
        checked = (
            f"checked {_count(len(vault.sources), 'Source')} "
            f"({_count(personas, 'Persona')}), "
            f"{_count(len(vault.persons), 'Person')} "
            f"({_count(conclusions, 'Conclusion')}), "
            f"{_count(len(vault.questions), 'Research Question')}, "
            f"{len(vault.media)} Media"
        )
    if not findings:
        return f"{checked}: no problems found"
    severities = Counter(finding.severity for finding in findings)
    return (
        f"{checked}: {_count(severities['error'], 'error')}, "
        f"{_count(severities['warning'], 'warning')}, "
        f"{_count(severities['info'], 'info line')}"
    )


def _count(number: int, noun: str) -> str:
    return f"{number} {noun}" if number == 1 else f"{number} {noun}s"


def _media_add(file: Path, root: Path) -> int:
    if not file.is_file():
        print(f"error: {file}: no such file", file=sys.stderr)
        return 1
    try:
        media_id, added = media.add_media(root, file)
    except media.RegistryError as problem:
        print(f"error: {root / media.REGISTRY}: {problem}", file=sys.stderr)
        return 1
    if not added:
        print(f"{file} is already registered; not added again", file=sys.stderr)
    print(media_id)
    return 0


def _new(root: Path, command: str, args: argparse.Namespace) -> int:
    try:
        if command == "id":
            print(create.fresh_id(root, args.kind))
        else:
            path, id = create.create(root, command, args.label)
            print(f"created {path} ({id})")
    except create.CreateFailed as problem:
        print(f"error: {problem}", file=sys.stderr)
        return 1
    return 0


def _import_gedcom(root: Path, export: Path) -> int:
    try:
        report = gedcom_import.import_gedcom(root, export)
    except gedcom_import.ImportFailed as problem:
        print(f"error: {problem}", file=sys.stderr)
        return 1
    source = report.source
    if report.already_imported:
        print(
            f"{export.name} is already imported as {source.file} ({source.id}); "
            "nothing changed"
        )
    else:
        print(
            f"imported {export.name} as {source.file} ({source.id}): "
            f"{report.personas} Personas, {report.events} events, "
            f"{report.parent_child + report.spouses} relationships "
            f"({report.parent_child} parent-child, {report.spouses} spouse)"
        )
    if report.uninterpreted:
        print("not interpreted, kept verbatim as raw GEDCOM:")
        for (path, where), count in Counter(report.uninterpreted).items():
            print(f"  {count} × {path} (on {where})")
    return 0


def _vault_init(root: Path) -> int:
    # Re-running init on a Vault's own root fills in what is missing; anywhere else
    # inside a Vault it would nest a second one.
    folder = Path(os.path.abspath(root))
    enclosing = find_root(folder)
    if enclosing not in (None, folder):
        print(
            f"error: {folder} is inside the Research Vault at {enclosing}; "
            "a Vault cannot hold another",
            file=sys.stderr,
        )
        return 1
    report = scaffold.init_vault(root)
    for path in sorted(report.created):
        print(f"created {path}")
    for path in sorted(report.skipped):
        print(
            f"skipped {path}: differs from the toolkit's version, not overwritten; "
            "run `gtool vault update` to review it"
        )
    _report_hooks(root, scaffold.enable_hooks(root))
    if shutil.which("git-lfs") is None:
        print(
            "warning: Git LFS is not installed, so Media files would be committed directly "
            "into git history. Install it (https://git-lfs.com) and run `git lfs install`.",
            file=sys.stderr,
        )
    return 0


def _report_hooks(root: Path, report: scaffold.HookReport) -> None:
    if report.status is scaffold.HookStatus.ENABLED:
        print(
            f"enabled the pre-commit hook (core.hooksPath = {report.hooks_path}): "
            "every commit now runs gtool check"
        )
    elif report.status is scaffold.HookStatus.NOT_A_REPOSITORY:
        print(
            "to check every commit, run this after `git init` in the Vault: "
            f"git -C {shlex.quote(str(root))} config core.hooksPath {scaffold.HOOKS}"
        )
    elif report.status is scaffold.HookStatus.ELSEWHERE:
        print(
            f"warning: core.hooksPath is already set to {report.hooks_path}, so the "
            f"Vault's pre-commit hook ({scaffold.HOOKS}/pre-commit) is not enabled; "
            "left it untouched",
            file=sys.stderr,
        )
