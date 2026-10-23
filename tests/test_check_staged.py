import subprocess
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


def git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "commit.gpgsign=false", *args],
        cwd=repo,
        check=True,
        capture_output=True,
    )


def write(vault: Path, relative_path: str, text: str) -> None:
    path = vault / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


@pytest.fixture
def vault(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> Path:
    """A new Vault at the root of a git repo, committed on main."""
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.name", "Test Researcher")
    git(root, "config", "user.email", "researcher@example.com")
    main(["vault", "init", str(root)])
    git(root, "add", "-A")
    git(root, "commit", "--no-verify", "-q", "-m", "commit")
    capsys.readouterr()
    return root


def add_media(vault: Path, capsys: pytest.CaptureFixture[str]) -> str:
    scan = vault.parent / "scan.jpg"
    scan.write_bytes(b"synthetic image bytes")
    main(["media", "add", str(scan), "--vault", str(vault)])
    return capsys.readouterr().out.strip()


def test_checks_the_staged_file_not_the_one_on_disk(
    vault: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write(vault, "sources/census.md", "# No frontmatter at all\n")
    git(vault, "add", "sources/census.md")
    write(vault, "sources/census.md", CENSUS)
    write(vault, "sources/draft.md", "id: not staged, and no frontmatter\n")

    exit_code = main(["check", "--staged", str(vault)])

    out = capsys.readouterr().out
    assert exit_code == 1
    assert "error: sources/census.md: frontmatter is missing" in out
    assert "sources/draft.md" not in out


def test_a_file_deleted_on_disk_but_still_staged_is_checked(
    vault: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write(vault, "sources/census.md", "# No frontmatter at all\n")
    git(vault, "add", "sources/census.md")
    (vault / "sources/census.md").unlink()

    exit_code = main(["check", "--staged", str(vault)])

    assert exit_code == 1
    assert "sources/census.md: frontmatter" in capsys.readouterr().out


def test_media_files_are_checksummed_on_disk(
    vault: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    media_id = add_media(vault, capsys)
    git(vault, "add", "-A")
    location = f"media/{media_id}.jpg"
    (vault / location).write_bytes(b"altered after it was staged")

    exit_code = main(["check", "--staged", str(vault)])

    assert exit_code == 1
    assert (
        f"error: media.yaml: Media '{media_id}' file '{location}' does not match "
        "its recorded SHA-256 checksum" in capsys.readouterr().out
    )


def test_a_source_refers_to_media_registered_only_on_disk(
    vault: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    media_id = add_media(vault, capsys)
    write(
        vault,
        "sources/census.md",
        CENSUS.replace("---\nid:", f"---\nmedia: [{media_id}]\nid:"),
    )
    git(vault, "add", "sources/census.md")

    staged_exit = main(["check", "--staged", str(vault)])
    staged_out = capsys.readouterr().out
    disk_exit = main(["check", str(vault)])

    assert staged_exit == 1
    assert f"refers to Media '{media_id}', which is not registered" in staged_out
    assert disk_exit == 0


def test_an_unstaged_media_registry_is_an_error(
    vault: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    git(vault, "rm", "-q", "--cached", "media.yaml")

    exit_code = main(["check", "--staged", str(vault)])

    assert exit_code == 1
    assert (
        "error: media.yaml: Media registry is not staged; run `git add media.yaml`"
        in capsys.readouterr().out
    )


def test_with_since_reviews_what_is_staged_against_the_ref(
    vault: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write(vault, "sources/census.md", CENSUS)
    git(vault, "add", "sources/census.md")
    git(vault, "commit", "--no-verify", "-q", "-m", "commit")
    write(vault, "sources/census.md", CENSUS.replace("Jno. Smyth", "John Smith"))
    git(vault, "add", "sources/census.md")
    write(vault, "sources/census.md", CENSUS)

    staged_exit = main(["check", "--staged", "--since", "main", str(vault)])
    staged_out = capsys.readouterr().out
    disk_exit = main(["check", "--since", "main", str(vault)])

    assert staged_exit == 1
    assert (
        "error: sources/census.md: Persona 'persona-aaaa1111' was edited without "
        "a new transcription correction" in staged_out
    )
    assert disk_exit == 0


def test_a_vault_outside_any_git_repo_is_a_usage_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main(["vault", "init", str(tmp_path / "vault")])
    capsys.readouterr()

    exit_code = main(["check", "--staged", str(tmp_path / "vault")])

    assert exit_code == 2
    assert "cannot read the Vault as staged" in capsys.readouterr().err
