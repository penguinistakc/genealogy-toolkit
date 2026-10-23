# Versions measure impact on a Research Vault, not on the code

The toolkit follows Semantic Versioning, but its public interface is what a Research Vault and its users depend on, not the Python code: the Vault file format (frontmatter fields and what they mean), the `check` rules (a new error can fail a Vault, and its pre-commit hook, that passed before), the command line (commands, flags, exit codes and JSON output, which agents and scripts rely on), and the files `vault init` ships (agent instructions, templates, the hook). The `genealogy_toolkit` Python modules are internal and may change in any release. A version is chosen by asking what an existing Vault or script would have to do, not by how much code changed.

- **Before 1.0**, a minor release (0.x.0) carries anything that could need attention in an existing Vault or script: a format change, a new `check` error, a changed flag or output, changed shipped files, or a new command. A patch release (0.x.y) carries only fixes that cannot affect an existing Vault.
- **1.0** is released once the first slice has been proved end to end in the researcher's real Vault, when the format is stable enough that breaking it means a migration.
- **After 1.0**, breaking any part of the interface needs a major release, and is preceded by a deprecation: the old behavior or field is reported as a `check` warning in at least one minor release before the major release removes it.

The version is kept in `pyproject.toml` (bumped with `uv version --bump`) rather than derived from git tags, which would need a different build backend and one more dependency to trust. A release is a `vX.Y.Z` tag on `main` whose version matches `pyproject.toml`, built and published by CI rather than on a workstation, so that publishing to PyPI later is one added step rather than a new process. Releases happen when the researcher decides `main` holds a change worth having in the Vault; agents may prepare a release but never publish one.

## Consequences

Because a format change affects every Vault, the Vault records the format version it is written in, separately from the toolkit version, and `check` refuses a format it doesn't understand; format changes ship with a migration. That must exist before 1.0, because it cannot be added to Vaults other people already have.
