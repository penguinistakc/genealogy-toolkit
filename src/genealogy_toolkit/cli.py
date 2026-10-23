"""Command-line entry point: `gtool <command> ...`."""

import argparse
import dataclasses
import json
import shutil
import sys
from collections.abc import Sequence
from pathlib import Path

from genealogy_toolkit import scaffold, validation
from genealogy_toolkit.vault import load_vault


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="gtool")
    commands = parser.add_subparsers(dest="command", required=True)

    vault = commands.add_parser("vault", help="manage a Research Vault")
    vault_commands = vault.add_subparsers(dest="vault_command", required=True)
    init = vault_commands.add_parser("init", help="lay out a new Research Vault")
    init.add_argument("path", type=Path, help="directory to create the Vault in")

    check = commands.add_parser("check", help="validate a Research Vault")
    check.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="output format; json is a list of {severity, file, message} (default: text)",
    )
    check.add_argument(
        "path",
        type=Path,
        nargs="?",
        default=Path("."),
        help="Vault directory (default: .)",
    )

    args = parser.parse_args(argv)
    if args.command == "check":
        return _check(args.path, args.format)
    return _vault_init(args.path)


def _check(root: Path, output_format: str) -> int:
    vault, findings = load_vault(root)
    findings += validation.validate(vault)
    if output_format == "json":
        print(
            json.dumps([dataclasses.asdict(finding) for finding in findings], indent=2)
        )
    else:
        for finding in findings:
            print(f"{finding.severity}: {finding.file}: {finding.message}")
    return 1 if any(f.severity == "error" for f in findings) else 0


def _vault_init(root: Path) -> int:
    report = scaffold.init_vault(root)
    for path in sorted(report.created):
        print(f"created {path}")
    for path in sorted(report.skipped):
        print(f"skipped {path}: differs from the toolkit's version, not overwritten")
    if shutil.which("git-lfs") is None:
        print(
            "warning: Git LFS is not installed, so Media files would be committed directly "
            "into git history. Install it (https://git-lfs.com) and run `git lfs install`.",
            file=sys.stderr,
        )
    return 0
