import hashlib
import re
from datetime import date
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


def media_file(tmp_path: Path, name: str, content: bytes = b"synthetic scan") -> Path:
    path = tmp_path / "incoming" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def registry(vault: Path) -> dict:
    return yaml.safe_load((vault / "media.yaml").read_text())["media"]


def add(vault: Path, file: Path, capsys: pytest.CaptureFixture[str]) -> str:
    assert main(["media", "add", str(file), "--vault", str(vault)]) == 0
    return capsys.readouterr().out.strip()


def test_add_copies_the_file_into_the_vault_and_registers_it(
    vault: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    content = b"synthetic census scan"
    file = media_file(tmp_path, "census 1850.JPG", content)

    media_id = add(vault, file, capsys)

    assert re.fullmatch(r"media-[0-9a-z]{8}", media_id)
    entry = registry(vault)[media_id]
    assert (vault / entry["location"]).read_bytes() == content
    assert entry["location"].startswith("media/")
    assert entry["sha256"] == hashlib.sha256(content).hexdigest()
    assert entry["type"] == "image/jpeg"
    assert entry["original_filename"] == "census 1850.JPG"
    assert entry["added"] == date.today()
    assert file.read_bytes() == content


def test_adding_an_already_registered_file_returns_its_id_and_creates_nothing(
    vault: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    first = add(vault, media_file(tmp_path, "scan.png", b"same bytes"), capsys)
    registry_before = (vault / "media.yaml").read_text()

    again = add(vault, media_file(tmp_path, "renamed copy.png", b"same bytes"), capsys)

    assert again == first
    assert (vault / "media.yaml").read_text() == registry_before
    assert len(list((vault / "media").iterdir())) == 1


def test_files_with_the_same_name_but_different_content_are_both_kept(
    vault: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    first = add(vault, media_file(tmp_path, "scan.png", b"page one"), capsys)
    second = add(vault, media_file(tmp_path, "scan.png", b"page two"), capsys)

    assert first != second
    entries = registry(vault)
    assert (vault / entries[first]["location"]).read_bytes() == b"page one"
    assert (vault / entries[second]["location"]).read_bytes() == b"page two"


@pytest.mark.parametrize(
    ("name", "media_type"),
    [
        ("will.pdf", "application/pdf"),
        ("headstone.tif", "image/tiff"),
        ("interview.mp3", "audio/mpeg"),
        ("interview.wav", "audio/"),
        ("cemetery.mp4", "video/mp4"),
        ("cemetery.MOV", "video/quicktime"),
    ],
)
def test_documents_audio_and_video_are_accepted_like_images(
    vault: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    name: str,
    media_type: str,
) -> None:
    media_id = add(vault, media_file(tmp_path, name), capsys)

    entry = registry(vault)[media_id]
    assert entry["type"].startswith(media_type)
    assert (vault / entry["location"]).is_file()


def test_the_registry_keeps_its_explanatory_comment(
    vault: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    comment = (vault / "media.yaml").read_text().split("media: {}")[0]

    add(vault, media_file(tmp_path, "scan.png"), capsys)

    assert (vault / "media.yaml").read_text().startswith(comment)


def test_adding_a_missing_file_fails(
    vault: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = main(
        ["media", "add", str(tmp_path / "nowhere.jpg"), "--vault", str(vault)]
    )

    assert exit_code == 1
    assert "nowhere.jpg" in capsys.readouterr().err
    assert registry(vault) == {}


def test_adding_outside_a_vault_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    not_a_vault = tmp_path / "empty"
    not_a_vault.mkdir()

    exit_code = main(
        [
            "media",
            "add",
            str(media_file(tmp_path, "scan.png")),
            "--vault",
            str(not_a_vault),
        ]
    )

    assert exit_code == 1
    assert "media.yaml" in capsys.readouterr().err
    assert list(not_a_vault.iterdir()) == []


def test_the_vault_defaults_to_the_current_directory(
    vault: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    file = media_file(tmp_path, "scan.png")
    monkeypatch.chdir(vault)

    assert main(["media", "add", str(file)]) == 0

    media_id = capsys.readouterr().out.strip()
    assert media_id in registry(vault)


def write(vault: Path, relative_path: str, text: str) -> None:
    path = vault / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def source_citing(*media_ids: str) -> str:
    return f"---\nid: source-aaaa1111\nmedia: [{', '.join(media_ids)}]\n---\n"


def test_a_source_citing_registered_media_passes(
    vault: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    media_id = add(vault, media_file(tmp_path, "scan.png"), capsys)
    write(vault, "sources/census.md", source_citing(media_id))

    exit_code = main(["check", str(vault)])

    assert capsys.readouterr().out == ""
    assert exit_code == 0


def test_a_source_citing_unregistered_media_is_reported(
    vault: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    media_id = add(vault, media_file(tmp_path, "scan.png"), capsys)
    write(vault, "sources/census.md", source_citing(media_id, "media-zzzz9999"))

    exit_code = main(["check", str(vault)])

    out = capsys.readouterr().out
    assert exit_code == 1
    assert (
        "error: sources/census.md: Source 'source-aaaa1111' refers to Media "
        "'media-zzzz9999', which is not registered in media.yaml"
    ) in out
    assert media_id not in out


def test_a_source_whose_media_is_not_a_list_of_ids_is_reported(
    vault: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write(
        vault, "sources/census.md", "---\nid: source-aaaa1111\nmedia: scan.png\n---\n"
    )

    exit_code = main(["check", str(vault)])

    assert exit_code == 1
    assert "error: sources/census.md: field 'media'" in capsys.readouterr().out


def test_registered_media_whose_file_is_missing_is_reported(
    vault: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    media_id = add(vault, media_file(tmp_path, "scan.png"), capsys)
    location = registry(vault)[media_id]["location"]
    (vault / location).unlink()

    exit_code = main(["check", str(vault)])

    assert exit_code == 1
    assert (
        f"error: media.yaml: Media '{media_id}' file '{location}' is missing"
        in capsys.readouterr().out
    )


def test_registered_media_whose_checksum_does_not_match_is_reported(
    vault: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    media_id = add(vault, media_file(tmp_path, "scan.png", b"original"), capsys)
    location = registry(vault)[media_id]["location"]
    (vault / location).write_bytes(b"swapped")

    exit_code = main(["check", str(vault)])

    assert exit_code == 1
    assert (
        f"error: media.yaml: Media '{media_id}' file '{location}' does not match "
        "its recorded SHA-256 checksum"
    ) in capsys.readouterr().out


@pytest.mark.parametrize(
    "text",
    [
        "media: [not, a, mapping]\n",
        "media:\n  media-aaaa1111: {location: media/a.png}\n",
        "media: {unclosed\n",
    ],
    ids=["not-a-mapping", "incomplete-entry", "invalid-yaml"],
)
def test_a_malformed_registry_is_reported(
    vault: Path, capsys: pytest.CaptureFixture[str], text: str
) -> None:
    write(vault, "media.yaml", text)

    exit_code = main(["check", str(vault)])

    assert exit_code == 1
    assert "error: media.yaml: Media registry" in capsys.readouterr().out


def test_a_missing_registry_is_reported(
    vault: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (vault / "media.yaml").unlink()

    exit_code = main(["check", str(vault)])

    assert exit_code == 1
    assert "error: media.yaml: Media registry is missing" in capsys.readouterr().out
