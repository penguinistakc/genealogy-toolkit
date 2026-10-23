import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from genealogy_toolkit.cli import main

CENSUS = """\
---
id: source-aaaa1111
title: 1850 census, Example County
classification: original
personas:
  - id: persona-aaaa1111
    names: [Jno. Smyth]
---
"""

GTOOL_BIN = str(Path(sys.executable).parent)
"""The directory holding the `gtool` under test, for the hook to find."""


def path_without_gtool() -> str:
    return os.pathsep.join(
        directory
        for directory in os.environ["PATH"].split(os.pathsep)
        if shutil.which("gtool", path=directory) is None
    )


def git(
    repo: Path, *args: str, path: str | None = None
) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PATH": path or f"{GTOOL_BIN}{os.pathsep}{os.environ['PATH']}"}
    return subprocess.run(
        ["git", "-c", "commit.gpgsign=false", *args],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def commit(repo: Path, path: str | None = None) -> subprocess.CompletedProcess[str]:
    git(repo, "add", "-A")
    return git(repo, "commit", "-q", "-m", "commit", path=path)


def write(vault: Path, relative_path: str, text: str) -> None:
    target = vault / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text)


@pytest.fixture(autouse=True)
def isolated_git_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the tester's own git config (a global core.hooksPath, say) out of the tests."""
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "gitconfig"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.name", "Test Researcher")
    git(root, "config", "user.email", "researcher@example.com")
    return root


def test_a_valid_vault_commits(repo: Path) -> None:
    main(["vault", "init", str(repo)])
    write(repo, "sources/census.md", CENSUS)

    result = commit(repo)

    assert result.returncode == 0, result.stderr
    assert git(repo, "log", "--oneline").stdout.strip()


def test_an_invalid_vault_is_refused_a_commit(repo: Path) -> None:
    main(["vault", "init", str(repo)])
    write(repo, "sources/census.md", "# No frontmatter at all\n")

    result = commit(repo)

    assert result.returncode != 0
    assert "sources/census.md: frontmatter" in result.stdout + result.stderr
    assert git(repo, "rev-parse", "--verify", "-q", "HEAD").returncode != 0


def hooks_path(repo: Path) -> str:
    return git(repo, "config", "--get", "core.hooksPath").stdout.strip()


def test_init_in_a_git_repository_enables_the_hook_and_says_so(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main(["vault", "init", str(repo)])

    assert hooks_path(repo) == ".githooks"
    assert "enabled the pre-commit hook" in capsys.readouterr().out


def test_rerunning_init_in_a_git_repository_does_nothing(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main(["vault", "init", str(repo)])
    capsys.readouterr()

    exit_code = main(["vault", "init", str(repo)])

    assert exit_code == 0
    assert hooks_path(repo) == ".githooks"
    assert capsys.readouterr().out == ""


def test_a_vault_in_a_subdirectory_of_a_repository_guards_its_commits(
    repo: Path,
) -> None:
    vault = repo / "research"
    main(["vault", "init", str(vault)])
    write(vault, "sources/census.md", "# No frontmatter at all\n")

    refused = commit(repo)
    write(vault, "sources/census.md", CENSUS)
    accepted = commit(repo)

    assert hooks_path(repo) == "research/.githooks"
    assert refused.returncode != 0
    assert "sources/census.md: frontmatter" in refused.stdout + refused.stderr
    assert accepted.returncode == 0, accepted.stderr


def test_init_outside_a_git_repository_says_how_to_enable_the_hook_later(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    vault = tmp_path / "vault"

    main(["vault", "init", str(vault)])

    out = capsys.readouterr().out
    assert f"git -C {vault} config core.hooksPath .githooks" in out


def test_the_printed_command_enables_the_hook_after_git_init(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    vault = tmp_path / "vault"
    main(["vault", "init", str(vault)])
    command = capsys.readouterr().out.split("in the Vault: ")[1].strip()
    git(vault, "init", "-q", "-b", "main")
    git(vault, "config", "user.name", "Test Researcher")
    git(vault, "config", "user.email", "researcher@example.com")

    subprocess.run(command, shell=True, check=True)
    write(vault, "sources/census.md", "# No frontmatter at all\n")

    assert commit(vault).returncode != 0


def test_init_never_overwrites_a_hooks_path_set_elsewhere(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    git(repo, "config", "core.hooksPath", "my-hooks")

    exit_code = main(["vault", "init", str(repo)])

    assert exit_code == 0
    assert hooks_path(repo) == "my-hooks"
    err = capsys.readouterr().err
    assert "core.hooksPath is already set to my-hooks" in err


def test_the_hook_says_how_to_install_gtool_when_it_is_missing(repo: Path) -> None:
    main(["vault", "init", str(repo)])
    write(repo, "sources/census.md", CENSUS)

    result = commit(repo, path=path_without_gtool())

    assert result.returncode != 0
    assert "gtool is not on the PATH" in result.stderr
    assert "uv tool install" in result.stderr


def commit_staged(repo: Path, *paths: str) -> subprocess.CompletedProcess[str]:
    """Stage only these paths and commit, leaving every other change unstaged."""
    git(repo, "add", "--", *paths)
    return git(repo, "commit", "-q", "-m", "commit")


def test_a_staged_invalid_file_is_refused_even_when_fixed_on_disk(repo: Path) -> None:
    main(["vault", "init", str(repo)])
    write(repo, "sources/census.md", "# No frontmatter at all\n")
    git(repo, "add", "-A")
    write(repo, "sources/census.md", CENSUS)

    result = git(repo, "commit", "-q", "-m", "commit")

    assert result.returncode != 0
    assert "sources/census.md: frontmatter" in result.stdout + result.stderr
    assert git(repo, "rev-parse", "--verify", "-q", "HEAD").returncode != 0


def test_an_unstaged_invalid_file_does_not_block_a_commit_of_valid_changes(
    repo: Path,
) -> None:
    main(["vault", "init", str(repo)])
    commit(repo)
    write(repo, "sources/census.md", CENSUS)
    write(repo, "sources/draft.md", "# No frontmatter at all\n")

    result = commit_staged(repo, "sources/census.md")

    assert result.returncode == 0, result.stdout + result.stderr
    assert git(repo, "ls-files", "sources").stdout.split() == ["sources/census.md"]


def test_a_vault_in_a_subdirectory_checks_what_is_staged(repo: Path) -> None:
    vault = repo / "research"
    main(["vault", "init", str(vault)])
    commit(repo)
    write(vault, "sources/census.md", CENSUS)
    write(vault, "sources/draft.md", "# No frontmatter at all\n")

    accepted = commit_staged(repo, "research/sources/census.md")
    refused = commit_staged(repo, "research/sources/draft.md")

    assert accepted.returncode == 0, accepted.stdout + accepted.stderr
    assert refused.returncode != 0
    assert "sources/draft.md: frontmatter" in refused.stdout + refused.stderr


def test_committing_named_files_checks_them_as_they_will_be_committed(
    repo: Path,
) -> None:
    main(["vault", "init", str(repo)])
    write(repo, "sources/census.md", CENSUS)
    commit(repo)
    write(repo, "sources/census.md", "# No frontmatter at all\n")

    # `git commit <path>` commits from a temporary index the hook must read.
    result = git(repo, "commit", "-q", "-m", "commit", "sources/census.md")

    assert result.returncode != 0
    assert "sources/census.md: frontmatter" in result.stdout + result.stderr
