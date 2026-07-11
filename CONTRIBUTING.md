# Contributing to ChronoMap

Thanks for considering it. This is a small project, so the process is
intentionally light.

## Setup

```bash
git clone https://github.com/Devansh-567/Chronomap.git
cd Chronomap
pip install -e ".[dev]"
pytest tests/ -v
```

## Before opening a PR

- Add or update a test for whatever you changed. If you fixed a bug,
  a regression test that fails on `main` and passes on your branch is
  the single most useful thing you can include.
- Run `pytest tests/ -v` and `black --check src/` locally.
- Keep PRs scoped to one thing. A 500-line PR that fixes a bug *and*
  reformats three unrelated files is much harder to review than two
  small PRs.

## What's useful right now

- Porting the original test suite over (see `CHANGELOG.md` — the package
  was split from a single file and the new test file is a starting point,
  not full coverage).
- Filling out `docs/API.md` with real examples per method.
- Anything in open issues tagged `good-first-issue`.

## Code style

- Type hints on public methods.
- Docstrings that explain *why*, not just restate the signature.
- No new required dependencies for the core package — optional
  dependencies (like pandas) belong behind `pip install chronomap[extra]`.

## Reporting bugs

Open an issue with a minimal reproduction. "It doesn't work" without a
snippet is hard to act on; a 5-line script that shows the wrong behavior
gets fixed a lot faster.
