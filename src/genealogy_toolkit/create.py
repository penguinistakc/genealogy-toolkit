"""`gtool new`: new Vault files from the Vault's own templates, and fresh IDs."""

from dataclasses import dataclass
from pathlib import Path

from genealogy_toolkit.ids import new_id
from genealogy_toolkit.vault import fill_template, load_vault, new_file


@dataclass(frozen=True)
class Kind:
    folder: str
    template: str
    field: str
    """The frontmatter field the label fills in."""
    heading: str = ""
    """The template's placeholder heading, if the label replaces it."""


KINDS = {
    "source": Kind("sources", "templates/source.md", "title"),
    "person": Kind("persons", "templates/person.md", "name", "# Person name"),
    "question": Kind("questions", "templates/research-question.md", "question"),
}


ID_KINDS = ["source", "persona", "person", "conclusion", "question"]
"""Kinds `gtool new id` hands out; Media IDs come only from `gtool media add`."""


class CreateFailed(Exception):
    pass


def create(root: Path, kind: str, label: str) -> tuple[str, str]:
    """Write a new file of this kind from the Vault's template; returns its path and ID."""
    spec = KINDS[kind]
    template = root / spec.template
    id = fresh_id(root, kind)
    if not template.is_file():
        raise CreateFailed(
            f"{spec.template} is missing from the Vault; "
            "run `gtool vault init` to restore it"
        )
    text = fill_template(template.read_text(), {"id": id, spec.field: label})
    if spec.heading:
        text = text.replace(f"\n{spec.heading}\n", f"\n# {label}\n", 1)
    path = new_file(spec.folder, label, id)
    (root / spec.folder).mkdir(exist_ok=True)
    with (root / path).open("x") as file:
        file.write(text)
    return path, id


def fresh_id(root: Path, kind: str) -> str:
    """A new ID of this kind that nothing in the Vault already uses."""
    vault, _ = load_vault(root)
    taken = (
        {source.id for source in vault.sources}
        | {persona.id for source in vault.sources for persona in source.personas}
        | {person.id for person in vault.persons}
        | {c.id for person in vault.persons for c in person.conclusions}
        | {question.id for question in vault.questions}
        | set(vault.media)
    )
    while (id := new_id(kind)) in taken:
        pass
    return id
