import hashlib
import shutil
from pathlib import Path
from typing import Any

import pytest
import yaml

from genealogy_toolkit.cli import main

TREE = Path(__file__).parent / "fixtures" / "tree.ged"


@pytest.fixture
def vault(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> Path:
    root = tmp_path / "vault"
    main(["vault", "init", str(root)])
    capsys.readouterr()
    return root


def sources(vault: Path) -> dict[str, dict[str, Any]]:
    """Each Source file in the Vault, by path, as its parsed frontmatter."""
    return {
        path.relative_to(vault).as_posix(): yaml.safe_load(
            path.read_text().split("---\n")[1]
        )
        for path in sorted((vault / "sources").glob("*.md"))
    }


def only_source(vault: Path) -> dict[str, Any]:
    (source,) = sources(vault).values()
    return source


def test_an_export_becomes_one_authored_source_with_a_persona_per_individual(
    vault: Path,
) -> None:
    exit_code = main(["import", "gedcom", str(TREE), "--vault", str(vault)])

    assert exit_code == 0
    source = only_source(vault)
    assert source["classification"] == "authored"
    assert source["id"].startswith("source-")
    assert len(source["personas"]) == 3
    assert all(p["id"].startswith("persona-") for p in source["personas"])


def personas_by_gedcom_id(vault: Path) -> dict[str, dict[str, Any]]:
    return {p["gedcom_id"]: p for p in only_source(vault)["personas"]}


def test_each_persona_carries_its_gedcom_identifier(vault: Path) -> None:
    main(["import", "gedcom", str(TREE), "--vault", str(vault)])

    assert list(personas_by_gedcom_id(vault)) == ["@I1@", "@I2@", "@I3@"]


def test_names_and_sex_are_recorded_as_stated(vault: Path) -> None:
    main(["import", "gedcom", str(TREE), "--vault", str(vault)])

    personas = personas_by_gedcom_id(vault)
    assert personas["@I1@"]["names"] == ["Ezekiel Q /Fictitious/"]
    assert personas["@I1@"]["sex"] == "M"
    assert personas["@I2@"]["names"] == ["Hepzibah /Madeup/", "Hepzibah /Fictitious/"]
    assert personas["@I2@"]["sex"] == "F"


def test_a_persona_whose_sex_is_not_stated_has_none_recorded(vault: Path) -> None:
    main(["import", "gedcom", str(TREE), "--vault", str(vault)])

    assert "sex" not in personas_by_gedcom_id(vault)["@I3@"]


def test_events_keep_their_dates_and_places_exactly_as_written(vault: Path) -> None:
    main(["import", "gedcom", str(TREE), "--vault", str(vault)])

    personas = personas_by_gedcom_id(vault)
    assert personas["@I1@"]["events"] == [
        {
            "type": "birth",
            "date": "abt 1842",
            "place": "Nowhere Township, Imaginary County, Ohio, USA",
        },
        {
            "type": "residence",
            "date": "1850",
            "place": "Nowhere Township, Imaginary County, Ohio, USA",
        },
        {"type": "death", "date": "12 Feb 1901", "place": "Ohio"},
    ]
    assert personas["@I2@"]["events"] == [
        {"type": "birth", "date": "bef 1848"},
        {"type": "burial", "place": "Pretend Cemetery\nImaginary County, Ohio"},
    ]
    assert personas["@I3@"]["events"] == [{"type": "birth", "date": "1871"}]


def snapshot(vault: Path) -> dict[str, bytes]:
    return {
        path.relative_to(vault).as_posix(): path.read_bytes()
        for path in vault.rglob("*")
        if path.is_file()
    }


def test_the_source_records_the_exports_checksum(vault: Path) -> None:
    main(["import", "gedcom", str(TREE), "--vault", str(vault)])

    assert (
        only_source(vault)["gedcom_sha256"]
        == hashlib.sha256(TREE.read_bytes()).hexdigest()
    )


def test_reimporting_the_same_export_changes_nothing(
    vault: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main(["import", "gedcom", str(TREE), "--vault", str(vault)])
    before = snapshot(vault)
    (path,) = sources(vault)
    renamed = tmp_path / "renamed.ged"
    shutil.copy(TREE, renamed)
    capsys.readouterr()

    exit_code = main(["import", "gedcom", str(renamed), "--vault", str(vault)])

    assert exit_code == 0
    assert snapshot(vault) == before
    assert f"already imported as {path}" in capsys.readouterr().out


def test_a_different_export_becomes_a_new_source_leaving_the_earlier_one_untouched(
    vault: Path, tmp_path: Path
) -> None:
    main(["import", "gedcom", str(TREE), "--vault", str(vault)])
    before = snapshot(vault)
    newer = tmp_path / "newer.ged"
    newer.write_text(TREE.read_text().replace("12 Feb 1901", "14 Feb 1901"))

    exit_code = main(["import", "gedcom", str(newer), "--vault", str(vault)])

    assert exit_code == 0
    after = snapshot(vault)
    assert {path: after[path] for path in before} == before
    assert len(sources(vault)) == 2


def test_the_import_reports_persona_and_event_counts(
    vault: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main(["import", "gedcom", str(TREE), "--vault", str(vault)])

    (path,) = sources(vault)
    out = capsys.readouterr().out
    assert f"imported tree.ged as {path}" in out
    assert "3 Personas, 6 events" in out


def test_the_imported_vault_passes_check(
    vault: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main(["import", "gedcom", str(TREE), "--vault", str(vault)])
    capsys.readouterr()

    exit_code = main(["check", str(vault)])

    assert exit_code == 0
    assert capsys.readouterr().out == ""


def test_the_source_is_titled_and_cited_as_an_ancestry_export(vault: Path) -> None:
    main(["import", "gedcom", str(TREE), "--vault", str(vault)])

    (path,) = sources(vault)
    source = only_source(vault)
    assert source["title"] == "Ancestry tree export (tree.ged)"
    assert source["repository"] == "Ancestry.com"
    assert "Ancestry.com Member Trees" in source["citation"]
    assert "3 Mar 2026" in source["citation"]
    assert "tree.ged" in source["citation"]
    assert path.startswith("sources/ancestry-tree-export-tree-ged-source-")


def write_gedcom(tmp_path: Path, name: str, lines: list[str]) -> Path:
    path = tmp_path / name
    path.write_bytes("\n".join(lines).encode())
    return path


def test_an_export_from_other_software_names_that_software(
    vault: Path, tmp_path: Path
) -> None:
    export = write_gedcom(
        tmp_path,
        "other.ged",
        ["0 HEAD", "1 SOUR PRETEND_APP", "2 NAME Pretend Genealogy App", "0 TRLR"],
    )

    main(["import", "gedcom", str(export), "--vault", str(vault)])

    source = only_source(vault)
    assert source["title"] == "GEDCOM export (other.ged)"
    assert source["repository"] == "Pretend Genealogy App"
    assert source["personas"] == []


def test_a_byte_order_mark_and_windows_line_endings_are_understood(
    vault: Path, tmp_path: Path
) -> None:
    export = tmp_path / "bom.ged"
    export.write_bytes(
        b"\xef\xbb\xbf0 HEAD\r\n0 @I9@ INDI\r\n1 NAME Zo\xc3\xab /Fictitious/\r\n0 TRLR\r\n"
    )

    main(["import", "gedcom", str(export), "--vault", str(vault)])

    assert personas_by_gedcom_id(vault)["@I9@"]["names"] == ["Zoë /Fictitious/"]


@pytest.mark.parametrize(
    ("contents", "problem"),
    [
        (b"0 HEAD\n1 CHAR ANSEL\n1 NOTE caf\xe9\n", "is not UTF-8"),
        (b"0 HEAD\nthis is not GEDCOM\n", "line 2 is not a GEDCOM line"),
        (b"0 HEAD\n2 DATE 1850\n", "line 2 has no parent record at level 1"),
    ],
    ids=["not-utf8", "not-a-gedcom-line", "skipped-level"],
)
def test_an_unreadable_export_is_reported_and_nothing_is_written(
    vault: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    contents: bytes,
    problem: str,
) -> None:
    export = tmp_path / "broken.ged"
    export.write_bytes(contents)
    before = snapshot(vault)

    exit_code = main(["import", "gedcom", str(export), "--vault", str(vault)])

    assert exit_code == 1
    assert f"error: broken.ged {problem}" in capsys.readouterr().err
    assert snapshot(vault) == before


def test_importing_into_a_directory_that_is_not_a_vault_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = main(["import", "gedcom", str(TREE), "--vault", str(tmp_path)])

    assert exit_code == 1
    assert "is not a Research Vault" in capsys.readouterr().err
    assert list(tmp_path.iterdir()) == []


def test_the_vault_defaults_to_the_current_directory(
    vault: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(vault)

    assert main(["import", "gedcom", str(TREE)]) == 0
    assert len(sources(vault)) == 1


FAMILIES = Path(__file__).parent / "fixtures" / "families.ged"


def relationships(vault: Path) -> dict[str, list[tuple[str, str]]]:
    """Each Persona's relationships as (type, the other Persona's GEDCOM identifier)."""
    personas = only_source(vault)["personas"]
    gedcom_ids = {p["id"]: p["gedcom_id"] for p in personas}
    return {
        p["gedcom_id"]: [
            (r["type"], gedcom_ids[r["persona"]]) for r in p.get("relationships", [])
        ]
        for p in personas
    }


def test_a_familys_partners_are_each_others_spouses(vault: Path) -> None:
    main(["import", "gedcom", str(FAMILIES), "--vault", str(vault)])

    found = relationships(vault)
    assert ("spouse", "@I2@") in found["@I1@"]
    assert ("spouse", "@I1@") in found["@I2@"]


def test_a_familys_children_and_partners_are_each_others_children_and_parents(
    vault: Path,
) -> None:
    main(["import", "gedcom", str(FAMILIES), "--vault", str(vault)])

    found = relationships(vault)
    assert found["@I4@"] == [("parent", "@I1@"), ("parent", "@I2@")]
    assert found["@I2@"] == [("spouse", "@I1@"), ("child", "@I4@")]


def test_a_person_in_several_families_gets_the_relationships_of_each(
    vault: Path,
) -> None:
    main(["import", "gedcom", str(FAMILIES), "--vault", str(vault)])

    assert relationships(vault)["@I1@"] == [
        ("spouse", "@I2@"),
        ("child", "@I4@"),
        ("spouse", "@I3@"),
        ("child", "@I5@"),
    ]


def test_a_child_of_one_family_can_be_a_partner_in_another(
    vault: Path, tmp_path: Path
) -> None:
    export = write_gedcom(
        tmp_path,
        "generations.ged",
        [
            "0 HEAD",
            "0 @I1@ INDI",
            "0 @I2@ INDI",
            "0 @I3@ INDI",
            "0 @F1@ FAM",
            "1 HUSB @I1@",
            "1 CHIL @I2@",
            "0 @F2@ FAM",
            "1 WIFE @I2@",
            "1 HUSB @I3@",
            "0 TRLR",
        ],
    )

    main(["import", "gedcom", str(export), "--vault", str(vault)])

    assert relationships(vault)["@I2@"] == [("parent", "@I1@"), ("spouse", "@I3@")]


def test_the_import_reports_relationship_counts(
    vault: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main(["import", "gedcom", str(FAMILIES), "--vault", str(vault)])

    assert "6 relationships (4 parent-child, 2 spouse)" in capsys.readouterr().out


def test_notes_are_kept_on_the_persona_verbatim(vault: Path) -> None:
    main(["import", "gedcom", str(FAMILIES), "--vault", str(vault)])

    personas = personas_by_gedcom_id(vault)
    assert personas["@I1@"]["notes"] == [
        "Family story says he walked to Ohio.\nUnverified."
    ]
    assert "notes" not in personas["@I2@"]
    assert personas["@I2@"]["events"][0]["notes"] == [
        "Worked out from her age on a pretend gravestone"
    ]


def test_source_references_are_kept_verbatim_as_gedcom_lines(vault: Path) -> None:
    main(["import", "gedcom", str(FAMILIES), "--vault", str(vault)])

    personas = personas_by_gedcom_id(vault)
    assert personas["@I5@"]["citations"] == ["1 SOUR @S1@\n2 PAGE Year: 1880"]
    assert personas["@I1@"]["events"][0]["citations"] == [
        (
            "2 SOUR @S1@\n"
            "3 PAGE Year: 1850; Census Place: Nowhere, Imaginary, Ohio; Roll: M000_000\n"
            "3 _APID 1,0000::1111"
        )
    ]
    assert "citations" not in personas["@I2@"]


def test_a_familys_events_are_recorded_on_each_partner(vault: Path) -> None:
    main(["import", "gedcom", str(FAMILIES), "--vault", str(vault)])

    personas = personas_by_gedcom_id(vault)
    marriage = {
        "type": "marriage",
        "date": "abt 1866",
        "place": "Imaginary County, Ohio",
    }
    assert marriage in personas["@I1@"]["events"]
    assert marriage in personas["@I2@"]["events"]
    assert marriage not in personas["@I4@"]["events"]


def test_an_unknown_tag_on_an_individual_is_kept_on_the_persona_as_raw_gedcom(
    vault: Path,
) -> None:
    main(["import", "gedcom", str(FAMILIES), "--vault", str(vault)])

    raw = personas_by_gedcom_id(vault)["@I1@"]["raw_gedcom"]
    assert "1 _MILT Served in a pretend regiment\n2 DATE 1862" in raw


def test_the_import_reports_what_it_could_not_interpret(
    vault: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main(["import", "gedcom", str(FAMILIES), "--vault", str(vault)])

    out = capsys.readouterr().out
    assert "not interpreted, kept verbatim as raw GEDCOM:" in out
    assert "  1 × INDI._MILT (on Personas)" in out


def test_name_parts_are_raw_gedcom_only_when_they_add_to_the_name(
    vault: Path,
) -> None:
    main(["import", "gedcom", str(FAMILIES), "--vault", str(vault)])

    personas = personas_by_gedcom_id(vault)
    assert personas["@I1@"]["raw_gedcom"] == [
        "1 _MILT Served in a pretend regiment\n2 DATE 1862"
    ]
    assert personas["@I5@"]["raw_gedcom"] == [
        "1 NAME Obadiah /Fictitious/\n2 GIVN Obie"
    ]


def test_records_outside_individuals_that_are_not_interpreted_are_kept_on_the_source(
    vault: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main(["import", "gedcom", str(FAMILIES), "--vault", str(vault)])

    assert only_source(vault)["raw_gedcom"] == [
        "0 @F1@ FAM\n1 CHIL @I4@\n2 _FREL Natural",
        "0 @F1@ FAM\n1 CHIL @I4@\n2 _MREL Natural",
        "0 @F2@ FAM\n1 CHIL @I9@",
        "0 @S1@ SOUR\n1 TITL 1850 Pretend Federal Census\n1 AUTH Ancestry.com",
    ]
    out = capsys.readouterr().out
    assert "  1 × FAM.CHIL._FREL (on the Source)" in out
    assert "  1 × FAM.CHIL (on the Source)" in out
    assert "  1 × SOUR (on the Source)" in out


def test_the_events_of_a_family_with_no_partners_are_kept_on_the_source(
    vault: Path, tmp_path: Path
) -> None:
    export = write_gedcom(
        tmp_path,
        "orphaned.ged",
        [
            "0 HEAD",
            "0 @I1@ INDI",
            "0 @F1@ FAM",
            "1 HUSB @I8@",
            "1 MARR",
            "2 DATE 1900",
            "2 _UNKN Pretend",
            "1 CHIL @I1@",
            "0 TRLR",
        ],
    )

    main(["import", "gedcom", str(export), "--vault", str(vault)])

    source = only_source(vault)
    assert source["raw_gedcom"] == [
        "0 @F1@ FAM\n1 HUSB @I8@",
        "0 @F1@ FAM\n1 MARR\n2 DATE 1900\n2 _UNKN Pretend",
    ]
    assert source["personas"][0]["events"] == []


def test_a_vault_with_imported_families_passes_check(
    vault: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main(["import", "gedcom", str(FAMILIES), "--vault", str(vault)])
    capsys.readouterr()

    exit_code = main(["check", str(vault)])

    assert exit_code == 0
    assert capsys.readouterr().out == ""
