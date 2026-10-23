import os
from pathlib import Path

import pytest

from genealogy_toolkit.cli import main


def test_init_creates_the_vault_layout(tmp_path: Path) -> None:
    vault = tmp_path / "vault"

    exit_code = main(["vault", "init", str(vault)])

    assert exit_code == 0
    for folder in ["sources", "persons", "questions", "media"]:
        assert (vault / folder).is_dir()


def test_init_provides_templates_for_each_kind_of_file(tmp_path: Path) -> None:
    vault = tmp_path / "vault"

    main(["vault", "init", str(vault)])

    templates = vault / "templates"
    assert (templates / "source.md").read_text().startswith("---\n")
    assert (templates / "person.md").read_text().startswith("---\n")
    question = (templates / "research-question.md").read_text()
    assert question.startswith("---\n")
    assert "## Research log" in question
    assert "## Proof Argument" in question


def test_init_creates_an_empty_media_registry(tmp_path: Path) -> None:
    vault = tmp_path / "vault"

    main(["vault", "init", str(vault)])

    assert (vault / "media.yaml").read_text().rstrip().endswith("media: {}")


def test_init_records_the_vault_format(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    vault = tmp_path / "vault"

    main(["vault", "init", str(vault)])

    assert "created vault.yaml" in capsys.readouterr().out
    record = (vault / "vault.yaml").read_text()
    assert record.startswith("#")
    assert record.rstrip().endswith("format: 1")


def test_init_records_the_format_of_an_existing_vault_without_one(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    vault = tmp_path / "vault"
    main(["vault", "init", str(vault)])
    (vault / "vault.yaml").unlink()
    capsys.readouterr()

    exit_code = main(["vault", "init", str(vault)])

    assert exit_code == 0
    assert capsys.readouterr().out.splitlines()[0] == "created vault.yaml"
    assert (vault / "vault.yaml").read_text().rstrip().endswith("format: 1")
    assert main(["check", str(vault)]) == 0


def test_init_never_overwrites_a_recorded_format(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    vault = tmp_path / "vault"
    main(["vault", "init", str(vault)])
    record = vault / "vault.yaml"
    record.write_text("format: 99\n")
    capsys.readouterr()

    main(["vault", "init", str(vault)])

    assert record.read_text() == "format: 99\n"
    assert "vault.yaml" not in capsys.readouterr().out


def test_init_stores_media_files_in_git_lfs(tmp_path: Path) -> None:
    vault = tmp_path / "vault"

    main(["vault", "init", str(vault)])

    attributes = (vault / ".gitattributes").read_text().splitlines()
    for extension in [
        "jpg",
        "JPG",
        "png",
        "tif",
        "pdf",
        "PDF",
        "mp3",
        "wav",
        "mp4",
        "MOV",
    ]:
        assert (
            f"media/**/*.{extension} filter=lfs diff=lfs merge=lfs -text" in attributes
        )


def test_init_gives_agents_the_vault_rules(tmp_path: Path) -> None:
    vault = tmp_path / "vault"

    main(["vault", "init", str(vault)])

    rules = (vault / "AGENTS.md").read_text()
    assert "pull request" in rules
    assert "never set or raise Confidence" in rules
    assert "exactly as the Source states" in rules
    assert "GLOSSARY.md" in rules
    assert "pre-commit hook runs `gtool check`" in rules
    assert "Never use `--no-verify`" in rules
    assert "@AGENTS.md" in (vault / "CLAUDE.md").read_text()


def test_rerunning_init_never_overwrites_a_changed_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    vault = tmp_path / "vault"
    main(["vault", "init", str(vault)])
    rules = vault / "AGENTS.md"
    rules.write_text("# My own rules\n")
    capsys.readouterr()

    exit_code = main(["vault", "init", str(vault)])

    assert exit_code == 0
    assert rules.read_text() == "# My own rules\n"
    assert "AGENTS.md" in capsys.readouterr().out


def test_rerunning_init_on_an_unchanged_vault_does_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    vault = tmp_path / "vault"
    main(["vault", "init", str(vault)])
    before = {path: path.read_text() for path in vault.rglob("*") if path.is_file()}
    capsys.readouterr()

    exit_code = main(["vault", "init", str(vault)])

    assert exit_code == 0
    assert {
        path: path.read_text() for path in vault.rglob("*") if path.is_file()
    } == before
    out = capsys.readouterr().out
    assert "created" not in out
    assert "skipped" not in out


def test_init_ships_an_executable_pre_commit_hook(tmp_path: Path) -> None:
    vault = tmp_path / "vault"

    main(["vault", "init", str(vault)])

    hook = vault / ".githooks" / "pre-commit"
    assert hook.read_text().startswith("#!/bin/sh\n")
    assert os.access(hook, os.X_OK)


def test_init_warns_when_git_lfs_is_not_installed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PATH", str(tmp_path / "empty-bin"))

    exit_code = main(["vault", "init", str(tmp_path / "vault")])

    assert exit_code == 0
    assert "Git LFS is not installed" in capsys.readouterr().err


def test_init_does_not_warn_when_git_lfs_is_installed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    git_lfs = bin_dir / "git-lfs"
    git_lfs.write_text("#!/bin/sh\n")
    git_lfs.chmod(0o755)
    monkeypatch.setenv("PATH", str(bin_dir))

    main(["vault", "init", str(tmp_path / "vault")])

    assert capsys.readouterr().err == ""
