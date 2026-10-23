import json
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
    events:
      - type: birth
        date: abt 1842
        place: Ohio
  - id: persona-bbbb2222
    names: [Mary Smyth]
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


def commit(repo: Path, message: str = "commit") -> None:
    git(repo, "add", "-A")
    git(repo, "commit", "--no-verify", "-q", "-m", message)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.name", "Test Researcher")
    git(root, "config", "user.email", "researcher@example.com")
    return root


@pytest.fixture
def vault(repo: Path, capsys: pytest.CaptureFixture[str]) -> Path:
    """A Vault at the root of a git repo, committed on main with one Source."""
    main(["vault", "init", str(repo)])
    write(repo, "sources/census.md", CENSUS)
    commit(repo)
    capsys.readouterr()
    return repo


def test_an_edited_persona_without_a_correction_is_an_error(
    vault: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write(vault, "sources/census.md", CENSUS.replace("Jno. Smyth", "John Smith"))

    exit_code = main(["check", "--since", "main", str(vault)])

    assert exit_code == 1
    assert (
        "error: sources/census.md: Persona 'persona-aaaa1111' was edited without "
        "a new transcription correction" in capsys.readouterr().out
    )


def test_an_unchanged_vault_reports_nothing(
    vault: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = main(["check", "--since", "main", str(vault)])

    assert exit_code == 0
    assert capsys.readouterr().out == ""


def test_reformatting_a_persona_without_changing_it_is_not_an_edit(
    vault: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write(
        vault,
        "sources/census.md",
        CENSUS.replace("names: [Jno. Smyth]", 'names:\n      - "Jno. Smyth"'),
    )

    assert main(["check", "--since", "main", str(vault)]) == 0
    assert capsys.readouterr().out == ""


def test_a_deleted_persona_is_an_error(
    vault: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write(
        vault,
        "sources/census.md",
        CENSUS.replace("  - id: persona-bbbb2222\n    names: [Mary Smyth]\n", ""),
    )

    exit_code = main(["check", "--since", "main", str(vault)])

    assert exit_code == 1
    assert (
        "error: sources/census.md: Persona 'persona-bbbb2222' was deleted"
        in capsys.readouterr().out
    )


def test_deleting_a_whole_source_reports_each_of_its_personas(
    vault: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (vault / "sources/census.md").unlink()

    exit_code = main(["check", "--since", "main", str(vault)])

    out = capsys.readouterr().out
    assert exit_code == 1
    assert "error: sources/census.md: Persona 'persona-aaaa1111' was deleted" in out
    assert "error: sources/census.md: Persona 'persona-bbbb2222' was deleted" in out


CORRECTED = CENSUS.replace("Jno. Smyth", "Jno. Smith").replace(
    "    names: [Jno. Smith]\n",
    "    names: [Jno. Smith]\n"
    "    corrections:\n"
    "      - Surname misread as Smyth; the 'i' is dotted on the original scan\n",
)


def test_an_edited_persona_with_a_new_correction_is_allowed(
    vault: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write(vault, "sources/census.md", CORRECTED)

    exit_code = main(["check", "--since", "main", str(vault)])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "error" not in out
    assert (
        "info: sources/census.md: Persona 'persona-aaaa1111' was edited with a "
        "transcription correction: Surname misread as Smyth" in out
    )


def test_an_edit_that_rewrites_an_earlier_correction_is_an_error(
    vault: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write(vault, "sources/census.md", CORRECTED)
    commit(vault)
    write(
        vault,
        "sources/census.md",
        CORRECTED.replace("Surname misread as Smyth", "Surname was wrong")
        .replace("abt 1842", "abt 1843")
        .replace(
            "on the original scan\n",
            "on the original scan\n      - Birth year misread\n",
        ),
    )

    exit_code = main(["check", "--since", "main", str(vault)])

    assert exit_code == 1
    assert (
        "error: sources/census.md: Persona 'persona-aaaa1111' was edited without "
        "a new transcription correction" in capsys.readouterr().out
    )


def person(confidence: str, *conclusions: str) -> str:
    extra = "".join(
        f"  - id: {conclusion}\n    confidence: Hypothesis\n"
        "    personas: [persona-bbbb2222]\n"
        for conclusion in conclusions
    )
    return (
        "---\nid: person-aaaa1111\nname: John Smith\nconclusions:\n"
        f"  - id: conclusion-aaaa1111\n    confidence: {confidence}\n"
        f"    personas: [persona-aaaa1111]\n{extra}---\n"
    )


def test_a_changed_confidence_is_listed_with_old_and_new_values(
    vault: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write(vault, "persons/john.md", person("Possible"))
    commit(vault)
    write(vault, "persons/john.md", person("Probable"))

    exit_code = main(["check", "--since", "main", str(vault)])

    assert exit_code == 0
    assert capsys.readouterr().out.splitlines() == [
        (
            "warning: persons/john.md: Conclusion 'conclusion-aaaa1111' Confidence "
            "changed from Possible to Probable"
        )
    ]


def test_new_personas_persons_and_conclusions_are_listed(
    vault: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write(
        vault,
        "sources/bible.md",
        "---\nid: source-bbbb2222\npersonas:\n  - id: persona-cccc3333\n---\n",
    )
    write(vault, "persons/john.md", person("Hypothesis", "conclusion-bbbb2222"))

    exit_code = main(["check", "--since", "main", str(vault)])

    out = capsys.readouterr().out.splitlines()
    assert exit_code == 0
    assert out == [
        "info: sources/bible.md: new Persona 'persona-cccc3333'",
        "info: persons/john.md: new Person 'person-aaaa1111'",
        (
            "info: persons/john.md: new Conclusion 'conclusion-aaaa1111' "
            "at Confidence Hypothesis"
        ),
        (
            "info: persons/john.md: new Conclusion 'conclusion-bbbb2222' "
            "at Confidence Hypothesis"
        ),
    ]


def test_a_new_conclusion_on_an_existing_person_is_listed(
    vault: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write(vault, "persons/john.md", person("Hypothesis"))
    commit(vault)
    write(vault, "persons/john.md", person("Hypothesis", "conclusion-bbbb2222"))

    main(["check", "--since", "main", str(vault)])

    assert capsys.readouterr().out.splitlines() == [
        (
            "info: persons/john.md: new Conclusion 'conclusion-bbbb2222' "
            "at Confidence Hypothesis"
        ),
    ]


def test_normal_check_findings_are_included_and_set_the_exit_code(
    vault: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write(vault, "persons/john.md", person("Certain"))

    exit_code = main(["check", "--since", "main", str(vault)])

    out = capsys.readouterr().out
    assert exit_code == 1
    assert (
        "error: persons/john.md: Conclusion 'conclusion-aaaa1111' has Confidence" in out
    )
    assert "info: persons/john.md: new Person 'person-aaaa1111'" in out


def test_compares_committed_changes_against_the_ref(
    vault: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    git(vault, "checkout", "-q", "-b", "proposal")
    write(vault, "sources/census.md", CENSUS.replace("Jno. Smyth", "John Smith"))
    commit(vault, "Proposal")

    exit_code = main(["check", "--since", "main", str(vault)])

    assert exit_code == 1
    assert "Persona 'persona-aaaa1111' was edited" in capsys.readouterr().out
    assert "John Smith" in (vault / "sources/census.md").read_text()


def test_a_vault_in_a_subdirectory_of_the_repo_is_reviewed(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    vault = repo / "research"
    main(["vault", "init", str(vault)])
    write(vault, "sources/census.md", CENSUS)
    write(repo, "sources/unrelated.md", "not part of the Vault\n")
    commit(repo)
    capsys.readouterr()
    (vault / "sources/census.md").unlink()

    exit_code = main(["check", "--since", "main", str(vault)])

    out = capsys.readouterr().out
    assert exit_code == 1
    assert "error: sources/census.md: Persona 'persona-aaaa1111' was deleted" in out
    assert "unrelated" not in out


@pytest.mark.parametrize("ref", ["no-such-branch", "--output=x"])
def test_an_unknown_ref_is_a_usage_error(
    vault: Path, capsys: pytest.CaptureFixture[str], ref: str
) -> None:
    exit_code = main(["check", f"--since={ref}", str(vault)])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert f"cannot read the Vault at '{ref}'" in captured.err
    assert captured.out == ""


def test_a_vault_outside_any_git_repo_is_a_usage_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "loose"
    main(["vault", "init", str(root)])
    capsys.readouterr()

    exit_code = main(["check", "--since", "main", str(root)])

    assert exit_code == 2
    assert "cannot read the Vault at 'main'" in capsys.readouterr().err


def test_json_output_carries_the_review_findings(
    vault: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write(vault, "sources/census.md", CORRECTED.replace("Mary Smyth", "Mary Smith"))
    main(["check", "--since", "main", str(vault)])
    text_lines = capsys.readouterr().out.splitlines()

    exit_code = main(["check", "--since", "main", "--format", "json", str(vault)])

    findings = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert {f["severity"] for f in findings} == {"error", "info"}
    assert [
        f"{f['severity']}: {f['file']}: {f['message']}" for f in findings
    ] == text_lines


JOHN = """\
---
id: person-aaaa1111
name: John Smith
conclusions:
  - id: conclusion-aaaa1111
    statement: Jno. Smyth in the 1850 census is John Smith
    confidence: Probable
    personas: [persona-aaaa1111]
  - id: conclusion-bbbb2222
    statement: John Smith was born about 1842 in Ohio
    confidence: Possible
    personas: [persona-aaaa1111]
---
"""

MARY = """\
---
id: person-bbbb2222
name: Mary Smith
conclusions:
  - id: conclusion-cccc3333
    statement: Mary Smyth in the 1850 census is Mary Smith
    confidence: Possible
    personas: [persona-bbbb2222]
---
"""

SECOND_CONCLUSION = """\
  - id: conclusion-bbbb2222
    statement: John Smith was born about 1842 in Ohio
    confidence: Possible
    personas: [persona-aaaa1111]
"""


@pytest.fixture
def persons(vault: Path) -> Path:
    """The Vault with two Persons and their Conclusions committed on main."""
    write(vault, "persons/john.md", JOHN)
    write(vault, "persons/mary.md", MARY)
    commit(vault)
    return vault


def test_a_deleted_conclusion_is_a_warning_with_what_it_said(
    persons: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write(persons, "persons/john.md", JOHN.replace(SECOND_CONCLUSION, ""))

    exit_code = main(["check", "--since", "main", str(persons)])

    assert exit_code == 0
    assert capsys.readouterr().out.splitlines() == [
        (
            "warning: persons/john.md: Conclusion 'conclusion-bbbb2222' of Person "
            "'person-aaaa1111' was deleted: \"John Smith was born about 1842 in "
            'Ohio" at Confidence Possible'
        )
    ]


def test_a_deleted_person_is_one_warning_counting_its_conclusions(
    persons: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (persons / "persons/john.md").unlink()

    exit_code = main(["check", "--since", "main", str(persons)])

    assert exit_code == 0
    assert capsys.readouterr().out.splitlines() == [
        (
            "warning: persons/john.md: Person 'person-aaaa1111' was deleted, "
            "with its 2 Conclusions"
        )
    ]


def test_a_conclusion_moved_to_another_person_is_a_warning(
    persons: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write(persons, "persons/john.md", JOHN.replace(SECOND_CONCLUSION, ""))
    write(
        persons,
        "persons/mary.md",
        MARY.replace("conclusions:\n", f"conclusions:\n{SECOND_CONCLUSION}"),
    )

    exit_code = main(["check", "--since", "main", str(persons)])

    assert exit_code == 0
    assert capsys.readouterr().out.splitlines() == [
        (
            "warning: persons/mary.md: Conclusion 'conclusion-bbbb2222' was moved "
            "from Person 'person-aaaa1111' to Person 'person-bbbb2222'"
        )
    ]


def test_a_conclusion_moved_off_a_deleted_person_is_still_reported(
    persons: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (persons / "persons/john.md").unlink()
    write(
        persons,
        "persons/mary.md",
        MARY.replace("conclusions:\n", f"conclusions:\n{SECOND_CONCLUSION}"),
    )

    main(["check", "--since", "main", str(persons)])

    assert capsys.readouterr().out.splitlines() == [
        (
            "warning: persons/john.md: Person 'person-aaaa1111' was deleted, "
            "with its 2 Conclusions"
        ),
        (
            "warning: persons/mary.md: Conclusion 'conclusion-bbbb2222' was moved "
            "from Person 'person-aaaa1111' to Person 'person-bbbb2222'"
        ),
    ]


def test_a_persona_moved_to_another_source_is_an_error(
    vault: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write(
        vault,
        "sources/census.md",
        CENSUS.replace("  - id: persona-bbbb2222\n    names: [Mary Smyth]\n", ""),
    )
    write(
        vault,
        "sources/bible.md",
        "---\nid: source-bbbb2222\npersonas:\n"
        "  - id: persona-bbbb2222\n    names: [Mary Smyth]\n---\n",
    )

    exit_code = main(["check", "--since", "main", str(vault)])

    assert exit_code == 1
    assert capsys.readouterr().out.splitlines() == [
        (
            "error: sources/bible.md: Persona 'persona-bbbb2222' was moved from "
            "Source 'source-aaaa1111' to Source 'source-bbbb2222'; a Persona records "
            "what its own Source states"
        )
    ]


@pytest.mark.parametrize(
    "relative_path, text",
    [("persons/john.md", JOHN), ("sources/census.md", CENSUS)],
)
def test_a_file_unreadable_at_the_ref_is_a_warning_not_new_content(
    vault: Path, capsys: pytest.CaptureFixture[str], relative_path: str, text: str
) -> None:
    write(vault, relative_path, text.replace("---\nid:", "---\nid: [", 1))
    commit(vault)
    write(vault, relative_path, text)

    exit_code = main(["check", "--since", "main", str(vault)])

    assert exit_code == 0
    assert capsys.readouterr().out.splitlines() == [
        (
            f"warning: {relative_path}: could not be read at main; changes to it "
            "cannot be reviewed"
        )
    ]


def test_json_output_carries_deletions_and_moves(
    persons: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (persons / "persons/mary.md").unlink()
    write(persons, "persons/john.md", JOHN.replace(SECOND_CONCLUSION, ""))
    write(
        persons,
        "sources/bible.md",
        "---\nid: source-bbbb2222\npersonas:\n"
        "  - id: persona-bbbb2222\n    names: [Mary Smyth]\n---\n",
    )
    write(
        persons,
        "sources/census.md",
        CENSUS.replace("  - id: persona-bbbb2222\n    names: [Mary Smyth]\n", ""),
    )
    main(["check", "--since", "main", str(persons)])
    text_lines = capsys.readouterr().out.splitlines()

    exit_code = main(["check", "--since", "main", "--format", "json", str(persons)])

    findings = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert [(f["severity"], f["file"]) for f in findings] == [
        ("error", "sources/bible.md"),
        ("warning", "persons/mary.md"),
        ("warning", "persons/john.md"),
    ]
    assert [
        f"{f['severity']}: {f['file']}: {f['message']}" for f in findings
    ] == text_lines
