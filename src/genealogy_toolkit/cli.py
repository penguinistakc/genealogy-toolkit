"""Command-line entry point: `gtool <command> ...`."""

import argparse
import dataclasses
import json
import shlex
import shutil
import sys
from collections.abc import Sequence
from pathlib import Path

from genealogy_toolkit import gedcom_import, media, review, scaffold, validation
from genealogy_toolkit.vault import GitError, load_vault


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="gtool")
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
    import_gedcom.add_argument("file", type=Path, help="the GEDCOM export")
    import_gedcom.add_argument(
        "--vault",
        type=Path,
        default=Path("."),
        help="Vault directory (default: .)",
    )

    args = parser.parse_args(argv)
    if args.command == "check":
        return _check(args.path, args.format, args.since)
    if args.command == "media":
        return _media_add(args.file, args.vault)
    if args.command == "import":
        return _import_gedcom(args.vault, args.file)
    return _vault_init(args.path)


def _check(root: Path, output_format: str, since: str | None) -> int:
    vault, findings = load_vault(root)
    findings += validation.validate(vault)
    if since is not None:
        try:
            before, _ = load_vault(root, since)
        except GitError as problem:
            print(f"gtool: error: {problem}", file=sys.stderr)
            return 2
        findings += review.review(before, vault, since)
    if output_format == "json":
        print(
            json.dumps([dataclasses.asdict(finding) for finding in findings], indent=2)
        )
    else:
        for finding in findings:
            print(f"{finding.severity}: {finding.file}: {finding.message}")
    return 1 if any(f.severity == "error" for f in findings) else 0


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
            f"{report.personas} Personas, {report.events} events"
        )
    return 0


def _vault_init(root: Path) -> int:
    report = scaffold.init_vault(root)
    for path in sorted(report.created):
        print(f"created {path}")
    for path in sorted(report.skipped):
        print(f"skipped {path}: differs from the toolkit's version, not overwritten")
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
