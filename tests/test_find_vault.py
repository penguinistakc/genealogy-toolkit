"""Commands find the Vault root from any folder inside it, as git finds a repository."""

import subprocess
from pathlib import Path

import pytest
import yaml

from genealogy_toolkit.cli import main

BROKEN = "# No frontmatter at all\n"
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
TREE = Path(__file__).parent / "fixtures" / "tree.ged"


@pytest.fixture
def vault(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> Path:
    root = tmp_path / "vault"
    main(["vault", "init", str(root)])
    capsys.readouterr()
    return root


@pytest.mark.parametrize("folder", ["sources", "persons", "sources/1850/ohio"])
def test_check_from_a_folder_inside_the_vault_checks_the_whole_vault(
    vault: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    folder: str,
) -> None:
    (vault / "sources/1850/ohio").mkdir(parents=True)
    (vault / "persons/broken.md").write_text(BROKEN)
    monkeypatch.chdir(vault / folder)

    exit_code = main(["check"])

    assert exit_code == 1
    assert capsys.readouterr().out.splitlines()[:-1] == [
        (
            "error: persons/broken.md: frontmatter is missing: "
            "the file must start with a '---' line"
        )
    ]


def test_a_vault_made_before_format_records_is_found_by_its_media_registry(
    vault: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    (vault / "vault.yaml").unlink()
    (vault / "persons/broken.md").write_text(BROKEN)
    monkeypatch.chdir(vault / "sources")

    exit_code = main(["check"])

    assert exit_code == 1
    assert "error: persons/broken.md: frontmatter" in capsys.readouterr().out


def test_a_given_folder_inside_the_vault_finds_it_too(
    vault: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (vault / "persons/broken.md").write_text(BROKEN)

    exit_code = main(["check", str(vault / "questions")])

    assert exit_code == 1
    assert "error: persons/broken.md: frontmatter" in capsys.readouterr().out


def test_check_outside_any_vault_says_so(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    exit_code = main(["check"])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert captured.err == f"error: {Path.cwd()} is not inside a Research Vault\n"
    assert captured.out == ""
    assert list(tmp_path.iterdir()) == []


def test_a_folder_that_does_not_exist_is_an_error(
    vault: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(vault)

    exit_code = main(["new", "person", "Ezekiel", "--vault", "sorces"])

    assert exit_code == 1
    assert capsys.readouterr().err == "error: sorces: no such folder\n"
    assert list((vault / "persons").iterdir()) == []


def git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "commit.gpgsign=false", *args],
        cwd=repo,
        check=True,
        capture_output=True,
    )


@pytest.fixture
def nested(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> Path:
    """A Vault in a folder of its git repository, committed on main."""
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.name", "Test Researcher")
    git(repo, "config", "user.email", "researcher@example.com")
    main(["vault", "init", str(repo / "research")])
    git(repo, "add", "-A")
    git(repo, "commit", "--no-verify", "-q", "-m", "commit")
    capsys.readouterr()
    return repo / "research"


def test_check_staged_from_a_folder_inside_a_nested_vault(
    nested: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    (nested / "persons/broken.md").write_text(BROKEN)
    git(nested, "add", "persons/broken.md")
    monkeypatch.chdir(nested / "sources")

    exit_code = main(["check", "--staged"])

    assert exit_code == 1
    assert capsys.readouterr().out.splitlines()[:-1] == [
        (
            "error: persons/broken.md: frontmatter is missing: "
            "the file must start with a '---' line"
        )
    ]


def test_check_since_from_a_folder_inside_a_nested_vault(
    nested: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    (nested / "sources/census.md").write_text(CENSUS)
    monkeypatch.chdir(nested / "sources")

    exit_code = main(["check", "--since", "main"])

    assert exit_code == 0
    assert "info: sources/census.md:" in capsys.readouterr().out


def test_media_add_from_a_folder_inside_the_vault_takes_the_file_from_there(
    vault: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    (vault / "sources/scan.png").write_bytes(b"synthetic image bytes")
    monkeypatch.chdir(vault / "sources")

    exit_code = main(["media", "add", "scan.png"])

    assert exit_code == 0
    media_id = capsys.readouterr().out.strip()
    registry = yaml.safe_load((vault / "media.yaml").read_text())
    location = registry["media"][media_id]["location"]
    assert (vault / location).read_bytes() == b"synthetic image bytes"
    assert not (vault / "sources/media.yaml").exists()


def test_import_gedcom_from_a_folder_inside_the_vault(
    vault: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(vault / "persons")

    exit_code = main(["import", "gedcom", str(TREE)])

    assert exit_code == 0
    assert capsys.readouterr().out.startswith("imported tree.ged as sources/")
    assert len(list((vault / "sources").glob("*.md"))) == 1
    assert not (vault / "persons/sources").exists()


@pytest.mark.parametrize("kind, folder", [("source", "sources"), ("person", "persons")])
def test_new_from_a_folder_inside_the_vault_writes_into_the_vault(
    vault: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
    folder: str,
) -> None:
    monkeypatch.chdir(vault / "questions")

    exit_code = main(["new", kind, "Ezekiel"])

    assert exit_code == 0
    path = capsys.readouterr().out.split()[1]
    assert path.startswith(f"{folder}/")
    assert (vault / path).is_file()


@pytest.mark.parametrize(
    "command",
    [
        ["media", "add", "scan.png"],
        ["import", "gedcom", str(TREE)],
        ["new", "person", "Ezekiel"],
        ["new", "id", "persona"],
    ],
    ids=["media", "import", "new", "new-id"],
)
def test_other_commands_outside_any_vault_say_so(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    command: list[str],
) -> None:
    (tmp_path / "scan.png").write_bytes(b"synthetic image bytes")
    monkeypatch.chdir(tmp_path)

    exit_code = main(command)

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.err == f"error: {Path.cwd()} is not inside a Research Vault\n"
    assert captured.out == ""
    assert [path.name for path in tmp_path.iterdir()] == ["scan.png"]


@pytest.mark.parametrize("inside", ["sources", "notes/drafts"])
def test_vault_init_inside_a_vault_is_refused(
    vault: Path, capsys: pytest.CaptureFixture[str], inside: str
) -> None:
    before = sorted(vault.rglob("*"))

    exit_code = main(["vault", "init", str(vault / inside)])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.err == (
        f"error: {vault / inside} is inside the Research Vault at {vault}; "
        "a Vault cannot hold another\n"
    )
    assert captured.out == ""
    assert sorted(vault.rglob("*")) == before


def test_vault_init_on_the_vault_root_from_inside_it_still_works(
    vault: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    (vault / "templates/person.md").unlink()
    monkeypatch.chdir(vault / "sources")

    exit_code = main(["vault", "init", ".."])

    assert exit_code == 0
    assert "created templates/person.md" in capsys.readouterr().out


@pytest.mark.parametrize(
    "command",
    [["new", "source", "1850 census"], ["new", "id", "persona"]],
    ids=["new", "new-id"],
)
def test_a_vault_found_without_its_sources_folder_still_works(
    vault: Path, capsys: pytest.CaptureFixture[str], command: list[str]
) -> None:
    (vault / "sources").rmdir()

    exit_code = main([*command, "--vault", str(vault)])

    assert exit_code == 0
    assert capsys.readouterr().err == ""
