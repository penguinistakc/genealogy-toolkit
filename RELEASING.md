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

1. **Checks the tag against `pyproject.toml`.** It fails before building anything unless the tag is exactly `v` followed by the version in `pyproject.toml`.
2. **Finds the release notes.** It takes the text under `## X.Y.Z - YYYY-MM-DD` in `CHANGELOG.md`, up to the next level-two (`##`) heading, and fails if that section is missing or empty.
3. **Runs lint and the tests**, with the same tools and commands as CI.
4. **Builds** the wheel and source distribution with `uv build`.
5. **Publishes a GitHub Release** for the tag, titled `vX.Y.Z`, whose notes are that changelog section, with the wheel and source distribution attached.

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

Every development tool runs at an exact version: `mise.toml` pins task, pre-commit, node, python and uv, and `Taskfile.yml`'s `lint:markdown` task pins markdownlint-cli2 (`npx --yes markdownlint-cli2@X.Y.Z`).

Versions alone don't fix what gets downloaded, so two more things are pinned:

- `mise.lock` records the exact download URL and SHA-256 checksum of each `mise.toml` tool for macOS arm64 and Linux x64. mise refuses a download that doesn't match it, and CI installs only what it lists: `jdx/mise-action` runs `mise install --locked` whenever a `mise.lock` is present.
- `pyproject.toml`'s build backend, `uv_build`, is pinned to the same version as uv, so `uv build` uses the copy of the backend bundled in uv instead of downloading one from PyPI.

To bump one:

1. **Pick a release at least seven days old**, so a bad upstream release has time to be noticed and pulled before it runs here. Take the date from the publisher, not from memory: the project's GitHub releases page, <https://nodejs.org/dist/index.json> for node (LTS releases only), python.org for python, and `npm view markdownlint-cli2 time` for markdownlint-cli2. Python is also a build: mise downloads CPython from [python-build-standalone](https://github.com/astral-sh/python-build-standalone/releases), which rebuilds every CPython version every few days, so also pick a python-build-standalone release (a date tag such as `20261013`) at least seven days old that includes the version.
2. **Change it**, on a new branch: the tool's line in `mise.toml`, or the version after `markdownlint-cli2@` in `Taskfile.yml`. Then:
   - For a `mise.toml` tool, run `mise lock <tool>` to record the new version's downloads in `mise.lock`, for the platforms already in the file.
   - For python, `mise lock python` records the newest python-build-standalone build of the version. If that build is under seven days old, change the release tag in both `[tools.python."platforms.…"]` URLs in `mise.lock` (it appears twice in each URL), delete their `checksum` and `provenance` lines, and run `mise lock python` again: mise keeps a build that is already in the lockfile, verifies its GitHub attestation and fills in its checksum from that release's `SHA256SUMS`. Don't use `mise lock --bump`, which moves to the newest build.
   - For uv, also change `uv_build==X.Y.Z` in `pyproject.toml`'s `[build-system]` to the new uv version (every uv release has a `uv_build` release of the same number on PyPI). `uv build -v` should then print ``Using bundled `uv_build` backend`` and download no backend.

   Run `mise install`, `task lint` and `task test` locally, and read `git diff -- mise.lock`: only the bumped tool's entries should change, and every URL should be the publisher's.
3. **Let CI check it.** Open a pull request listing the tool, the old and new version (for python, the python-build-standalone release too), the release date and the publisher; CI installs the pinned versions from `mise.lock` on Linux and macOS and must pass before it merges.
