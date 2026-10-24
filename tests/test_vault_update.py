import hashlib
import io
import os
from pathlib import Path

import pytest
import yaml

from genealogy_toolkit.cli import main


class Terminal(io.StringIO):
    """A researcher at a terminal, typing the given answers."""

    def isatty(self) -> bool:
        return True


@pytest.fixture
def vault(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> Path:
    root = tmp_path / "vault"
    main(["vault", "init", str(root)])
    capsys.readouterr()
    return root


def files(vault: Path) -> dict[Path, bytes]:
    return {path: path.read_bytes() for path in vault.rglob("*") if path.is_file()}


def shipped(vault: Path) -> dict[str, str]:
    return yaml.safe_load((vault / "vault.yaml").read_text()).get("shipped", {})


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def written_by_an_older_gtool(vault: Path, path: str, text: str) -> None:
    """Make the Vault's copy of a shipped file one an older gtool wrote and recorded."""
    (vault / path).write_text(text)
    record = yaml.safe_load((vault / "vault.yaml").read_text())
    record["shipped"][path] = sha256(text)
    (vault / "vault.yaml").write_text(yaml.dump(record))


def test_update_on_a_current_vault_prints_nothing_and_changes_nothing(
    vault: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("sys.stdin", Terminal("y\n" * 20))
    before = files(vault)

    exit_code = main(["vault", "update", str(vault)])

    assert exit_code == 0
    assert capsys.readouterr().out == ""
    assert files(vault) == before


def test_update_creates_a_missing_shipped_file_and_records_it(
    vault: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    template = vault / "templates" / "person.md"
    shipped_text = template.read_text()
    template.unlink()

    exit_code = main(["vault", "update", str(vault)])

    assert exit_code == 0
    assert capsys.readouterr().out == "created templates/person.md\n"
    assert template.read_text() == shipped_text
    assert shipped(vault)["templates/person.md"] == sha256(shipped_text)


def test_without_a_terminal_update_only_reports_a_differing_file(
    vault: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("y\n"))
    written_by_an_older_gtool(vault, "AGENTS.md", "# Old rules\n")
    before = files(vault)

    exit_code = main(["vault", "update", str(vault)])

    assert exit_code == 0
    out = capsys.readouterr().out
    lines = out.splitlines()
    assert (
        lines[0]
        == "AGENTS.md differs from the toolkit's version: not edited since gtool wrote it"
    )
    assert lines[1] == "--- AGENTS.md (this Vault)"
    assert lines[2].startswith("+++ AGENTS.md (gtool ")
    assert "-# Old rules" in lines
    assert "+# Research Vault: rules for agents" in lines
    assert "nothing replaced" in lines[-1]
    assert "replace AGENTS.md" not in out
    assert files(vault) == before


def test_update_says_when_a_differing_file_was_edited_in_the_vault(
    vault: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    written_by_an_older_gtool(vault, "AGENTS.md", "# Old rules\n")
    (vault / "AGENTS.md").write_text("# Old rules\n\nMy own rule.\n")

    main(["vault", "update", str(vault)])

    assert (
        "AGENTS.md differs from the toolkit's version: edited in this Vault"
        in capsys.readouterr().out.splitlines()
    )


def test_update_says_a_file_may_have_been_edited_when_there_is_no_record(
    vault: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    (vault / "vault.yaml").write_text("format: 1\n")
    (vault / "AGENTS.md").write_text("# Old rules\n")

    main(["vault", "update", str(vault)])

    assert (
        "AGENTS.md differs from the toolkit's version: may have been edited"
        in capsys.readouterr().out.splitlines()
    )


def test_update_replaces_a_differing_file_when_the_researcher_says_yes(
    vault: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    shipped_text = (vault / "AGENTS.md").read_text()
    written_by_an_older_gtool(vault, "AGENTS.md", "# Old rules\n")
    monkeypatch.setattr("sys.stdin", Terminal("yes\n"))

    exit_code = main(["vault", "update", str(vault)])

    assert exit_code == 0
    out = capsys.readouterr().out
    assert (
        "replace AGENTS.md with the toolkit's version? [y/N] replaced AGENTS.md" in out
    )
    assert (vault / "AGENTS.md").read_text() == shipped_text
    assert shipped(vault)["AGENTS.md"] == sha256(shipped_text)
    assert main(["vault", "update", str(vault)]) == 0
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("answer", ["n\n", "\n", "maybe\n", ""])
def test_update_keeps_a_differing_file_without_a_yes(
    answer: str,
    vault: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    written_by_an_older_gtool(vault, "AGENTS.md", "# Old rules\n")
    monkeypatch.setattr("sys.stdin", Terminal(answer))
    before = files(vault)

    main(["vault", "update", str(vault)])

    assert "kept AGENTS.md" in capsys.readouterr().out
    assert files(vault) == before


def test_update_asks_file_by_file(
    vault: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    written_by_an_older_gtool(vault, "AGENTS.md", "# Old rules\n")
    written_by_an_older_gtool(vault, "templates/source.md", '---\nid: ""\n---\n')
    monkeypatch.setattr("sys.stdin", Terminal("n\ny\n"))

    main(["vault", "update", str(vault)])

    out = capsys.readouterr().out
    assert "kept AGENTS.md" in out
    assert "replaced templates/source.md" in out
    assert (vault / "AGENTS.md").read_text() == "# Old rules\n"


def test_a_replaced_hook_stays_executable(
    vault: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hook = vault / ".githooks" / "pre-commit"
    written_by_an_older_gtool(vault, ".githooks/pre-commit", "#!/bin/sh\nexit 0\n")
    hook.chmod(0o644)
    monkeypatch.setattr("sys.stdin", Terminal("y\n"))

    main(["vault", "update", str(vault)])

    assert "gtool check --staged" in hook.read_text()
    assert os.access(hook, os.X_OK)


def test_update_at_a_terminal_records_shipped_files_that_already_match(
    vault: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("sys.stdin", Terminal(""))
    (vault / "vault.yaml").write_text("format: 1\n")

    main(["vault", "update", str(vault)])

    assert capsys.readouterr().out == (
        f"recorded checksums for {len(shipped(vault))} shipped files in vault.yaml\n"
    )
    rules = (vault / "AGENTS.md").read_bytes()
    assert shipped(vault)["AGENTS.md"] == hashlib.sha256(rules).hexdigest()
    assert main(["check", str(vault)]) == 0


def test_without_a_terminal_update_adds_no_records(
    vault: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("y\n"))
    (vault / "vault.yaml").write_text("format: 1\n")
    (vault / "AGENTS.md").write_text("# Old rules\n")
    before = files(vault)

    main(["vault", "update", str(vault)])

    assert "may have been edited" in capsys.readouterr().out
    assert files(vault) == before


def test_update_leaves_the_media_registry_to_the_vault(
    vault: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scan = tmp_path / "scan.jpg"
    scan.write_bytes(b"synthetic scan")
    main(["media", "add", str(scan), "--vault", str(vault)])
    monkeypatch.setattr("sys.stdin", Terminal("y\n"))
    registry = (vault / "media.yaml").read_text()
    capsys.readouterr()

    main(["vault", "update", str(vault)])

    assert capsys.readouterr().out == ""
    assert (vault / "media.yaml").read_text() == registry


def test_update_updates_a_vault_made_before_the_format_record(
    vault: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    (vault / "vault.yaml").unlink()

    exit_code = main(["vault", "update", str(vault)])

    assert exit_code == 0
    assert capsys.readouterr().out == "created vault.yaml\n"
    assert yaml.safe_load((vault / "vault.yaml").read_text())["format"] == 1
    assert main(["check", str(vault)]) == 0


def test_update_refuses_a_folder_that_is_not_a_vault(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = main(["vault", "update", str(tmp_path)])

    assert exit_code == 1
    assert "is not inside a Research Vault" in capsys.readouterr().err
    assert list(tmp_path.iterdir()) == []


def test_update_refuses_a_vault_in_a_format_it_does_not_understand(
    vault: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (vault / "vault.yaml").write_text("format: 99\n")
    (vault / "AGENTS.md").unlink()

    exit_code = main(["vault", "update", str(vault)])

    assert exit_code == 1
    assert "newer than this gtool understands" in capsys.readouterr().err
    assert not (vault / "AGENTS.md").exists()


def test_update_works_from_a_folder_inside_the_vault(
    vault: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("sys.stdin", Terminal("y\n"))
    (vault / "AGENTS.md").unlink()
    monkeypatch.chdir(vault / "sources")

    exit_code = main(["vault", "update"])

    assert exit_code == 0
    assert capsys.readouterr().out == "created AGENTS.md\n"
    assert (vault / "AGENTS.md").is_file()
