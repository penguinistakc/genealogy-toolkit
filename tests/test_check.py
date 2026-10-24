import json
from pathlib import Path

import pytest

from genealogy_toolkit.cli import main


@pytest.fixture
def vault(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> Path:
    root = tmp_path / "vault"
    main(["vault", "init", str(root)])
    capsys.readouterr()
    return root


def test_a_fresh_vault_passes(vault: Path, capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["check", str(vault)])

    assert exit_code == 0
    assert "error" not in capsys.readouterr().out


def write(vault: Path, relative_path: str, text: str) -> None:
    path = vault / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def test_a_vault_without_a_format_record_passes_as_the_first_format(
    vault: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (vault / "vault.yaml").unlink()

    exit_code = main(["check", str(vault)])

    assert exit_code == 0
    assert capsys.readouterr().out == ""


def test_a_newer_format_is_an_error_saying_to_upgrade_gtool(
    vault: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write(vault, "vault.yaml", "format: 99\n")
    write(vault, "sources/census.md", "# No frontmatter at all\n")

    exit_code = main(["check", str(vault)])

    out = capsys.readouterr().out
    assert exit_code == 1
    assert out.startswith("error: vault.yaml: ")
    assert "format 99" in out
    assert "upgrade gtool" in out
    # A Vault in a format gtool doesn't understand is refused, not misread.
    assert "sources/census.md" not in out


@pytest.mark.parametrize(
    "text",
    [
        "format: [unclosed\n",
        "- format\n- 1\n",
        "# nothing recorded\n",
        "version: 1\n",
        "format: one\n",
        "format: '1'\n",
        "format: 1.5\n",
        "format: true\n",
        "format: 0\n",
    ],
    ids=[
        "invalid-yaml",
        "not-a-mapping",
        "empty",
        "missing",
        "word",
        "quoted",
        "fraction",
        "boolean",
        "before-the-first",
    ],
)
def test_a_malformed_or_unknown_format_is_an_error_naming_the_file(
    vault: Path, capsys: pytest.CaptureFixture[str], text: str
) -> None:
    write(vault, "vault.yaml", text)

    exit_code = main(["check", str(vault)])

    out = capsys.readouterr().out
    assert exit_code == 1
    assert out.startswith("error: vault.yaml: ")
    assert len(out.splitlines()) == 1


def test_json_output_carries_the_format_error(
    vault: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write(vault, "vault.yaml", "format: 99\n")

    exit_code = main(["check", "--format", "json", str(vault)])

    [finding] = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert finding["severity"] == "error"
    assert finding["file"] == "vault.yaml"


@pytest.mark.parametrize(
    "text",
    [
        "# No frontmatter at all\n",
        "---\nid: source-aaaa1111\ntitle: [unclosed\n---\n",
        "---\n- just\n- a list\n---\n",
        "---\nid: source-aaaa1111\n",
    ],
    ids=["missing", "invalid-yaml", "not-a-mapping", "unterminated"],
)
def test_malformed_frontmatter_is_reported(
    vault: Path, capsys: pytest.CaptureFixture[str], text: str
) -> None:
    write(vault, "sources/census.md", text)

    exit_code = main(["check", str(vault)])

    assert exit_code == 1
    assert "error: sources/census.md: frontmatter" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("relative_path", "text", "field"),
    [
        ("persons/john.md", "---\nname: John\n---\n", "id"),
        ("questions/q.md", "---\nid: ''\n---\n", "id"),
        (
            "sources/census.md",
            "---\nid: source-aaaa1111\npersonas: none\n---\n",
            "personas",
        ),
        (
            "sources/census.md",
            "---\nid: source-aaaa1111\npersonas:\n  - names: [John]\n---\n",
            "personas[0].id",
        ),
        (
            "sources/census.md",
            (
                "---\nid: source-aaaa1111\npersonas:\n  - id: persona-aaaa1111\n"
                "    names: John\n---\n"
            ),
            "personas[0].names",
        ),
        (
            "sources/census.md",
            (
                "---\nid: source-aaaa1111\npersonas:\n  - id: persona-aaaa1111\n"
                "    events:\n      - date: abt 1842\n---\n"
            ),
            "personas[0].events[0].type",
        ),
        (
            "persons/john.md",
            (
                "---\nid: person-aaaa1111\nconclusions:\n  - id: conclusion-aaaa1111\n"
                "    personas: persona-aaaa1111\n---\n"
            ),
            "conclusions[0].personas",
        ),
    ],
    ids=[
        "missing-id",
        "empty-id",
        "personas-not-a-list",
        "persona-without-id",
        "persona-names-not-a-list",
        "event-without-type",
        "personas-not-a-list-in-conclusion",
    ],
)
def test_missing_or_mistyped_fields_are_reported(
    vault: Path,
    capsys: pytest.CaptureFixture[str],
    relative_path: str,
    text: str,
    field: str,
) -> None:
    write(vault, relative_path, text)

    exit_code = main(["check", str(vault)])

    assert exit_code == 1
    assert f"error: {relative_path}: field '{field}'" in capsys.readouterr().out


def test_duplicate_ids_are_reported_wherever_they_occur(
    vault: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write(
        vault,
        "sources/census.md",
        "---\nid: source-aaaa1111\npersonas:\n  - id: persona-aaaa1111\n"
        "  - id: persona-aaaa1111\n---\n",
    )
    write(vault, "persons/john.md", "---\nid: source-aaaa1111\n---\n")

    exit_code = main(["check", str(vault)])

    out = capsys.readouterr().out
    assert exit_code == 1
    assert "error: sources/census.md: duplicate ID 'persona-aaaa1111'" in out
    assert (
        "error: persons/john.md: duplicate ID 'source-aaaa1111' (also in sources/census.md)"
        in out
    )


def test_a_relationship_to_a_persona_outside_its_source_is_reported(
    vault: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write(
        vault,
        "sources/census.md",
        "---\nid: source-aaaa1111\npersonas:\n  - id: persona-aaaa1111\n"
        "    relationships:\n      - type: parent\n        persona: persona-bbbb2222\n---\n",
    )
    write(
        vault,
        "sources/bible.md",
        "---\nid: source-bbbb2222\npersonas:\n  - id: persona-bbbb2222\n---\n",
    )

    exit_code = main(["check", str(vault)])

    assert exit_code == 1
    assert (
        "error: sources/census.md: Persona 'persona-aaaa1111' has a relationship to "
        "'persona-bbbb2222', which is not a Persona in this Source"
    ) in capsys.readouterr().out


def test_a_persona_listed_as_its_own_relative_is_reported_once(
    vault: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write(
        vault,
        "sources/census.md",
        "---\nid: source-aaaa1111\npersonas:\n  - id: persona-aaaa1111\n"
        "    relationships:\n      - type: parent\n        persona: persona-aaaa1111\n"
        "      - type: spouse\n        persona: persona-bbbb2222\n"
        "  - id: persona-bbbb2222\n---\n",
    )

    exit_code = main(["check", str(vault)])

    assert exit_code == 1
    assert capsys.readouterr().out.splitlines() == [
        (
            "error: sources/census.md: Persona 'persona-aaaa1111' has a parent "
            "relationship to 'persona-aaaa1111', which is the Persona itself"
        )
    ]


def source_with_marriage(spouse: str) -> str:
    return (
        "---\nid: source-aaaa1111\npersonas:\n"
        "  - id: persona-aaaa1111\n"
        f"    events:\n      - type: marriage\n        spouse: {spouse}\n"
        "      - type: birth\n"
        "  - id: persona-bbbb2222\n---\n"
    )


def test_a_family_event_with_its_spouse_in_the_same_source_passes(
    vault: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write(vault, "sources/marriages.md", source_with_marriage("persona-bbbb2222"))

    exit_code = main(["check", str(vault)])

    assert exit_code == 0
    assert capsys.readouterr().out == ""


def test_a_family_event_with_a_spouse_outside_its_source_is_reported(
    vault: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write(vault, "sources/marriages.md", source_with_marriage("persona-cccc3333"))
    write(
        vault,
        "sources/bible.md",
        "---\nid: source-bbbb2222\npersonas:\n  - id: persona-cccc3333\n---\n",
    )

    exit_code = main(["check", str(vault)])

    assert exit_code == 1
    assert (
        "error: sources/marriages.md: Persona 'persona-aaaa1111' has a marriage event "
        "with spouse 'persona-cccc3333', which is not a Persona in this Source"
    ) in capsys.readouterr().out


def test_a_family_event_whose_spouse_is_the_persona_itself_is_reported(
    vault: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write(vault, "sources/marriages.md", source_with_marriage("persona-aaaa1111"))

    exit_code = main(["check", str(vault)])

    assert exit_code == 1
    assert (
        "error: sources/marriages.md: Persona 'persona-aaaa1111' has a marriage event "
        "with spouse 'persona-aaaa1111', which is the Persona itself"
    ) in capsys.readouterr().out


def test_a_conclusion_relying_on_a_missing_persona_is_reported(
    vault: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write(
        vault,
        "sources/census.md",
        "---\nid: source-aaaa1111\npersonas:\n  - id: persona-aaaa1111\n---\n",
    )
    write(
        vault,
        "persons/john.md",
        "---\nid: person-aaaa1111\nconclusions:\n  - id: conclusion-aaaa1111\n"
        "    confidence: Hypothesis\n    personas: [persona-aaaa1111, persona-zzzz9999]\n---\n",
    )

    exit_code = main(["check", str(vault)])

    out = capsys.readouterr().out
    assert exit_code == 1
    assert (
        "error: persons/john.md: Conclusion 'conclusion-aaaa1111' relies on "
        "Persona 'persona-zzzz9999', which does not exist"
    ) in out
    assert "persona-aaaa1111', which" not in out


def person_with_conclusion(confidence: str, proof: str = "") -> str:
    proof_line = f"    proof: {proof}\n" if proof else ""
    return (
        "---\nid: person-aaaa1111\nconclusions:\n  - id: conclusion-aaaa1111\n"
        f"    confidence: {confidence}\n    personas: []\n{proof_line}---\n"
    )


@pytest.mark.parametrize("confidence", ["Certain", "proved", "Likely"])
def test_confidence_outside_the_four_levels_is_reported(
    vault: Path, capsys: pytest.CaptureFixture[str], confidence: str
) -> None:
    write(vault, "persons/john.md", person_with_conclusion(confidence))

    exit_code = main(["check", str(vault)])

    assert exit_code == 1
    assert (
        f"error: persons/john.md: Conclusion 'conclusion-aaaa1111' has Confidence "
        f"'{confidence}'; it must be one of Proved, Probable, Possible, Hypothesis"
    ) in capsys.readouterr().out


@pytest.mark.parametrize("confidence", ["Probable", "Possible", "Hypothesis"])
def test_the_other_confidence_levels_pass(
    vault: Path, capsys: pytest.CaptureFixture[str], confidence: str
) -> None:
    write(vault, "persons/john.md", person_with_conclusion(confidence))

    assert main(["check", str(vault)]) == 0


def question(proof_argument: str) -> str:
    return (
        "---\nid: question-aaaa1111\nquestion: Who were John's parents?\n---\n\n"
        "# Who were John's parents?\n\n## Research log\n\nSearched the 1850 census.\n\n"
        f"## Proof Argument\n\n{proof_argument}\n"
    )


def test_a_proved_conclusion_with_a_proof_argument_passes(
    vault: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write(
        vault, "persons/john.md", person_with_conclusion("Proved", "question-aaaa1111")
    )
    write(vault, "questions/parents.md", question("Three independent Sources agree."))

    assert main(["check", str(vault)]) == 0


@pytest.mark.parametrize(
    ("proof", "proof_argument", "problem"),
    [
        ("", "Three independent Sources agree.", "names no Research Question"),
        (
            "question-zzzz9999",
            "Three independent Sources agree.",
            "'question-zzzz9999' does not exist",
        ),
        ("question-aaaa1111", "", "'question-aaaa1111' has no Proof Argument"),
        (
            "question-aaaa1111",
            "How the Evidence answers the question, including how conflicting Evidence was resolved.",
            "'question-aaaa1111' has no Proof Argument",
        ),
    ],
    ids=[
        "no-question",
        "missing-question",
        "empty-proof-argument",
        "template-placeholder",
    ],
)
def test_a_proved_conclusion_without_a_proof_argument_is_reported(
    vault: Path,
    capsys: pytest.CaptureFixture[str],
    proof: str,
    proof_argument: str,
    problem: str,
) -> None:
    write(vault, "persons/john.md", person_with_conclusion("Proved", proof))
    write(vault, "questions/parents.md", question(proof_argument))

    exit_code = main(["check", str(vault)])

    out = capsys.readouterr().out
    assert exit_code == 1
    assert (
        "error: persons/john.md: Conclusion 'conclusion-aaaa1111' is Proved but" in out
    )
    assert problem in out


def test_json_output_carries_the_same_findings(
    vault: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write(vault, "persons/john.md", person_with_conclusion("Certain"))
    write(vault, "questions/q.md", "no frontmatter\n")
    main(["check", str(vault)])
    text_lines = capsys.readouterr().out.splitlines()

    exit_code = main(["check", "--format", "json", str(vault)])

    findings = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert len(findings) == len(text_lines) == 2
    assert [
        f"{f['severity']}: {f['file']}: {f['message']}" for f in findings
    ] == text_lines


def test_json_output_for_a_clean_vault_is_an_empty_list(
    vault: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["check", "--format", "json", str(vault)]) == 0
    assert json.loads(capsys.readouterr().out) == []


def test_a_person_name_that_is_not_text_is_reported(
    vault: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write(vault, "persons/john.md", "---\nid: person-aaaa1111\nname: [John]\n---\n")

    exit_code = main(["check", str(vault)])

    assert exit_code == 1
    assert (
        "error: persons/john.md: field 'name' must be text" in capsys.readouterr().out
    )


@pytest.mark.parametrize("date", ["1850", "1850-03-04"])
def test_an_unquoted_date_is_reported_with_how_to_fix_it(
    vault: Path, capsys: pytest.CaptureFixture[str], date: str
) -> None:
    write(
        vault,
        "sources/census.md",
        "---\nid: source-aaaa1111\npersonas:\n  - id: persona-aaaa1111\n"
        f"    events:\n      - type: birth\n        date: {date}\n---\n",
    )

    exit_code = main(["check", str(vault)])

    assert exit_code == 1
    assert (
        "error: sources/census.md: field 'personas[0].events[0].date' must be text; "
        f'put it in quotes to keep it exactly as written, e.g. date: "{date}"'
    ) in capsys.readouterr().out
