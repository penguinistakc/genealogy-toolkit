"""Command-line entry point: `gtool <command> ...`."""

import argparse
import shutil
import sys
from collections.abc import Sequence
from pathlib import Path

from genealogy_toolkit import scaffold


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="gtool")
    commands = parser.add_subparsers(dest="command", required=True)

    vault = commands.add_parser("vault", help="manage a Research Vault")
    vault_commands = vault.add_subparsers(dest="vault_command", required=True)
    init = vault_commands.add_parser("init", help="lay out a new Research Vault")
    init.add_argument("path", type=Path, help="directory to create the Vault in")

    args = parser.parse_args(argv)
    report = scaffold.init_vault(args.path)
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
