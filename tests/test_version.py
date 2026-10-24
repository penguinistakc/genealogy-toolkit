import tomllib
from pathlib import Path

import pytest

from genealogy_toolkit.cli import main

PYPROJECT = Path(__file__).parent.parent / "pyproject.toml"


def test_version_prints_the_version_declared_in_pyproject(
    capsys: pytest.CaptureFixture[str],
) -> None:
    declared = tomllib.loads(PYPROJECT.read_text())["project"]["version"]

    with pytest.raises(SystemExit) as exit_info:
        main(["--version"])

    assert exit_info.value.code == 0
    assert capsys.readouterr().out == f"gtool {declared}\n"
