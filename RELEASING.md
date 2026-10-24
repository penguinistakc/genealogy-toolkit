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

Pushing the tag starts the [Release workflow](.github/workflows/release.yml), which:

1. **Checks the tag is on `main`.** It fails before anything else runs unless the tagged commit is the tip of `main` or one of its ancestors, so a tag on an unmerged branch never releases code that wasn't reviewed on `main`.
2. **Checks the tag against `pyproject.toml`.** It fails before building anything unless the tag is exactly `v` followed by the version in `pyproject.toml`.
3. **Finds the release notes.** It takes the text under `## X.Y.Z - YYYY-MM-DD` in `CHANGELOG.md`, up to the next level-two (`##`) heading, and fails if that section is missing or empty.
4. **Runs lint and the tests**, with the same tools and commands as CI.
5. **Builds** the wheel and source distribution with `uv build`.
6. **Publishes a GitHub Release** for the tag, titled `vX.Y.Z`, whose notes are that changelog section, with the wheel and source distribution attached.

Only the last step can write to the repository. If any earlier step fails, nothing is published: fix the problem on `main` through a pull request, then delete the tag (`git push origin :refs/tags/vX.Y.Z` and `git tag -d vX.Y.Z`) and tag the fixed commit.

### How to tell it succeeded

- The **Release** run for the tag is green on the [Actions page](https://github.com/penguinistakc/genealogy-toolkit/actions/workflows/release.yml) (or `gh run list --workflow release.yml`).
- The [Releases page](https://github.com/penguinistakc/genealogy-toolkit/releases) shows `vX.Y.Z` with the changelog section as its notes and two files attached: `genealogy_toolkit-X.Y.Z-py3-none-any.whl` and `genealogy_toolkit-X.Y.Z.tar.gz` (or `gh release view vX.Y.Z`).
- Installing the release reports its version:

  ```bash
  uv tool install git+https://github.com/penguinistakc/genealogy-toolkit@vX.Y.Z
  gtool --version
  ```

## Bumping a tool pin

Every development tool runs at an exact version: `mise.toml` pins task, pre-commit, node, python and uv, and `Taskfile.yml`'s `lint:markdown` task pins markdownlint-cli2 (`npx --yes markdownlint-cli2@X.Y.Z`). To bump one:

1. **Pick a release at least seven days old**, so a bad upstream release has time to be noticed and pulled before it runs here. Take the date from the publisher, not from memory: the project's GitHub releases page, <https://nodejs.org/dist/index.json> for node (LTS releases only), python.org for python, and `npm view markdownlint-cli2 time` for markdownlint-cli2.
2. **Change it in one place**, on a new branch: the tool's line in `mise.toml`, or the version after `markdownlint-cli2@` in `Taskfile.yml`. Run `mise install`, `task lint` and `task test` locally.
3. **Let CI check it.** Open a pull request listing the tool, the old and new version, the release date and the publisher; CI installs the pinned versions on Linux and macOS and must pass before it merges.
