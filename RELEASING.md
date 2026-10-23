# Releasing the toolkit

A release is a `vX.Y.Z` tag on `main` whose version matches `pyproject.toml`. Releases happen when the researcher decides `main` holds a change worth having in the Research Vault. An agent may prepare the release pull request, but only the researcher merges it and pushes the tag. **Agents never push release tags.**

The rules for choosing a version are in [ADR 0005](docs/adr/0005-versioning-by-impact-on-the-vault.md).

## Checklist

1. **Choose major, minor or patch** by asking what an existing Vault or script would have to do, per ADR 0005:
   - Before 1.0, **minor** (0.x.0) for anything that could need attention in an existing Vault or script: a Vault format change, a new `check` error, a changed flag or output, changed files that `vault init` ships, or a new command. **Patch** (0.x.y) only for fixes that cannot affect an existing Vault.
   - From 1.0, **major** for any break in the public interface, which must have been reported as a `check` warning in at least one earlier minor release.
   - Docs-only and test-only changes never need a release.
2. **Bump the version** on a new branch: `uv version --bump major|minor|patch`. This updates `pyproject.toml` and `uv.lock`.
3. **Turn "Unreleased" into the version's section** in [CHANGELOG.md](CHANGELOG.md): rename the heading to `## X.Y.Z - YYYY-MM-DD`, check that it reads as what the release means for a Vault (not as a commit log), and that it ends with "What to do in your Vault" when anything is needed. Start a new, empty "Unreleased" section above it.
4. **Open the release pull request** against `main`, titled `Release X.Y.Z`, with the changelog section as its description.
5. **After the researcher merges it**, the researcher tags the merge commit on `main` and pushes the tag:

   ```bash
   git switch main && git pull
   git tag vX.Y.Z
   git push origin vX.Y.Z
   ```

## After the tag

CI builds and publishes the release from the tag, not from anyone's workstation.

> **Placeholder:** the release workflow is being built in #44, which will describe here what it checks and publishes.

To install a specific release:

```bash
uv tool install git+https://github.com/penguinistakc/genealogy-toolkit@vX.Y.Z
```
