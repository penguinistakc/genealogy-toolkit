import re
from pathlib import Path

import pytest
import yaml

from genealogy_toolkit.cli import main


@pytest.fixture
def vault(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> Path:
    root = tmp_path / "vault"
    main(["vault", "init", str(root)])
    capsys.readouterr()
    return root


def frontmatter(path: Path) -> dict:
    return yaml.safe_load(path.read_text().split("---\n")[1])


def created(capsys: pytest.CaptureFixture[str]) -> tuple[str, str]:
    """The path and ID that `gtool new` reported."""
    match = re.fullmatch(r"created (\S+) \((\S+)\)\n", capsys.readouterr().out)
    assert match, "expected 'created <path> (<id>)'"
    return match[1], match[2]


def test_new_source_is_written_from_the_template_with_a_fresh_id_and_title(
    vault: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = main(
        ["new", "source", "1850 census, Nowhere Township", "--vault", str(vault)]
    )

    assert exit_code == 0
    path, id = created(capsys)
    assert re.fullmatch(r"source-[0-9a-z]{8}", id)
    assert path == f"sources/1850-census-nowhere-township-{id}.md"
    fields = frontmatter(vault / path)
    assert fields["id"] == id
    assert fields["title"] == "1850 census, Nowhere Township"
    text = (vault / path).read_text()
    assert "# full Citation, precise enough for someone else to find it" in text
    assert '#  - id: ""         # assigned by the toolkit' in text


def test_new_person_fills_in_the_name_and_heading(
    vault: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = main(["new", "person", "Ezekiel Q. Fictitious", "--vault", str(vault)])

    assert exit_code == 0
    path, id = created(capsys)
    assert re.fullmatch(r"person-[0-9a-z]{8}", id)
    assert path == f"persons/ezekiel-q-fictitious-{id}.md"
    assert frontmatter(vault / path) | {"id": id} == {
        "id": id,
        "name": "Ezekiel Q. Fictitious",
        "conclusions": [],
    }
    assert "\n# Ezekiel Q. Fictitious\n" in (vault / path).read_text()


def test_new_question_fills_in_the_question(
    vault: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = main(
        [
            "new",
            "question",
            'When was "Zeke" born?',
            "--vault",
            str(vault),
        ]
    )

    assert exit_code == 0
    path, id = created(capsys)
    assert re.fullmatch(r"question-[0-9a-z]{8}", id)
    assert path == f"questions/when-was-zeke-born-{id}.md"
    fields = frontmatter(vault / path)
    assert fields["id"] == id
    assert fields["question"] == 'When was "Zeke" born?'
    assert fields["status"] == "open"
    assert "## Proof Argument" in (vault / path).read_text()


@pytest.mark.parametrize(
    "kind", ["source", "persona", "person", "conclusion", "question"]
)
def test_new_id_prints_a_fresh_id_of_that_kind(
    vault: Path, capsys: pytest.CaptureFixture[str], kind: str
) -> None:
    exit_code = main(["new", "id", kind, "--vault", str(vault)])

    assert exit_code == 0
    assert re.fullmatch(rf"{kind}-[0-9a-z]{{8}}\n", capsys.readouterr().out)


def test_new_id_of_an_unknown_kind_is_a_usage_error(
    vault: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as exit:
        main(["new", "id", "media", "--vault", str(vault)])

    assert exit.value.code == 2
    assert "invalid choice: 'media'" in capsys.readouterr().err


def test_new_files_pass_check_as_created(
    vault: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main(["new", "source", "1850 census", "--vault", str(vault)])
    main(["new", "person", "Ezekiel Fictitious", "--vault", str(vault)])
    main(["new", "question", "When was Ezekiel born?", "--vault", str(vault)])
    capsys.readouterr()

    exit_code = main(["check", str(vault)])

    assert exit_code == 0
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize(
    "command",
    [["source", "1850 census"], ["person", "Ezekiel"], ["id", "persona"]],
    ids=["file", "file-person", "id"],
)
def test_a_directory_that_is_not_a_vault_is_an_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], command: list[str]
) -> None:
    exit_code = main(["new", *command, "--vault", str(tmp_path)])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert (
        f"error: {tmp_path} is not a Research Vault; run `gtool vault init` first"
        in captured.err
    )
    assert captured.out == ""
    assert list(tmp_path.iterdir()) == []


def test_a_missing_template_is_an_error(
    vault: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (vault / "templates/person.md").unlink()

    exit_code = main(["new", "person", "Ezekiel", "--vault", str(vault)])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert (
        "error: templates/person.md is missing from the Vault; "
        "run `gtool vault init` to restore it"
    ) in captured.err
    assert list((vault / "persons").iterdir()) == []


def test_a_label_with_yaml_and_regex_characters_is_kept_exactly(
    vault: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    title = 'Smith: "family" Bible, p. 3\\4 # \\1 ünïcode'

    main(["new", "source", title, "--vault", str(vault)])

    path, _ = created(capsys)
    assert frontmatter(vault / path)["title"] == title
    assert "ünïcode" in (vault / path).read_text()
