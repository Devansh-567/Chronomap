# Contributing to ChronoMap

Thanks for your interest in contributing! ChronoMap is a community project and every improvement helps.

## Table of contents

- [Getting started](#getting-started)
- [Development workflow](#development-workflow)
- [Testing](#testing)
- [Code style](#code-style)
- [Documentation](#documentation)
- [Submitting a pull request](#submitting-a-pull-request)
- [Release process](#release-process)
- [Good first issues](#good-first-issues)

---

## Getting started

### Prerequisites

- Python 3.8 or newer
- Git
- [pre-commit](https://pre-commit.com/) (strongly recommended)

### Fork and clone

```bash
git clone https://github.com/<your-username>/chronomap.git
cd chronomap
```

### Install in editable mode with dev dependencies

```bash
pip install -e ".[pandas,dev]"
```

### Install pre-commit hooks

```bash
pre-commit install
```

Hooks run automatically on every `git commit`. They check formatting, linting, and type errors locally before CI sees your code.

---

## Development workflow

```
main          ← protected, always deployable
  └── develop ← integration branch (PRs go here by default)
       └── feature/<short-name>   ← your work
       └── fix/<issue-number>-<short-name>
       └── docs/<topic>
```

1. Create a branch from `develop`:
   ```bash
   git checkout develop
   git pull origin develop
   git checkout -b feature/my-feature
   ```
2. Make your changes.
3. Add or update tests in `tests/`.
4. Update `CHANGELOG.md` under `[Unreleased]`.
5. Push and open a pull request against `develop`.

---

## Testing

```bash
# Run the full test suite
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=chronomap --cov-report=term-missing

# Run a specific test file or class
pytest tests/test_chronomap.py::TestLRUCache -v

# Run async tests only
pytest tests/ -k asyncio -v
```

New features need new tests. Bug fixes need a regression test that would have caught the bug. Coverage should not drop below 90%.

---

## Code style

ChronoMap uses [ruff](https://docs.astral.sh/ruff/) for linting and formatting.

```bash
# Check and auto-fix
ruff check --fix chronomap/ tests/

# Format
ruff format chronomap/ tests/

# Type check
mypy chronomap/ --ignore-missing-imports
```

Pre-commit runs all of these automatically. In CI, failures block merging.

Key conventions:
- Public methods must have type annotations and Google-style docstrings.
- No external dependencies in the core `chronomap/chronomap.py` — keep it zero-dep.
- `pickle` usage must carry a security note in the docstring.

---

## Documentation

Docs live in `docs/` and are built with [MkDocs Material](https://squidfunk.github.io/mkdocs-material/).

```bash
# Install doc dependencies
pip install -e ".[docs]"

# Live preview (auto-reloads on save)
mkdocs serve

# Build static site
mkdocs build --strict
```

When adding a new public method, update:
1. The docstring in `chronomap.py`
2. The relevant page under `docs/api/` or `docs/guide/`
3. `CHANGELOG.md` under `[Unreleased]`

---

## Submitting a pull request

1. Make sure all tests pass locally.
2. Make sure pre-commit hooks are all green.
3. Fill in the PR template completely.
4. Keep PRs focused — one logical change per PR makes review faster.
5. If your PR is a work in progress, open it as a draft.

A maintainer will review within a week. Expect at least one round of feedback.

---

## Release process

Releases are made by maintainers only. The process:

1. Merge `develop` → `main`.
2. Update `CHANGELOG.md`: move `[Unreleased]` entries to a new `[x.y.z] — YYYY-MM-DD` section.
3. Bump `version` in `pyproject.toml` and `chronomap/__init__.py`.
4. Push a tag: `git tag v2.3.0 && git push origin v2.3.0`
5. The `release.yml` workflow builds, publishes to PyPI, and creates a GitHub Release automatically.

---

## Good first issues

Look for issues labelled [`good first issue`](https://github.com/Devansh-567/chronomap/labels/good%20first%20issue). These are well-scoped tasks that don't require deep knowledge of the codebase.

Ideas for contributions that are always welcome:
- New examples in `examples/` (job queue, rate limiter, leaderboard, inventory tracker)
- Documentation improvements and typo fixes
- Additional test cases for edge conditions
- Performance benchmarks

Questions? Start a [GitHub Discussion](https://github.com/Devansh-567/chronomap/discussions).
