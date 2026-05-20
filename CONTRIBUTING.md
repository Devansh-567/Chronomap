# Contributing to ChronoMap

Thank you for taking the time to contribute! 🎉  
All kinds of contributions are welcome — bug fixes, new features, documentation improvements, and tests.

---

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Ways to Contribute](#ways-to-contribute)
- [Setting Up Your Environment](#setting-up-your-environment)
- [Project Structure](#project-structure)
- [Making Changes](#making-changes)
- [Running Tests](#running-tests)
- [Code Style](#code-style)
- [Submitting a Pull Request](#submitting-a-pull-request)
- [Getting Help](#getting-help)

---

## Code of Conduct

Be respectful and constructive. No harassment, discrimination, or gatekeeping.  
If you experience a problem, reach out at **devansh.jay.singh@gmail.com**.

---

## Ways to Contribute

- 🐛 **Fix a bug** — check open issues tagged `bug`
- ✨ **Add a feature** — check issues tagged `enhancement`
- 📝 **Improve docs** — fix typos, add examples, clarify explanations
- 🧪 **Write tests** — increase coverage for untested paths
- ⚡ **Improve performance** — check issues tagged `performance`
- 💡 **Suggest an idea** — open a new feature request issue

---

## Setting Up Your Environment

### 1. Fork and Clone

```bash
# Fork the repo on GitHub first, then clone your fork
git clone https://github.com/<your-username>/chronomap.git
cd chronomap
```

### 2. Create a Virtual Environment

```bash
python -m venv venv

# macOS / Linux
source venv/bin/activate

# Windows
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -e ".[pandas]"
pip install pytest pytest-cov pytest-asyncio black flake8
```

### 4. Verify Everything Works

```bash
pytest tests/ -v
```

All tests should pass. If anything fails before you've made any changes, open an issue.

### 5. Add the Upstream Remote

```bash
git remote add upstream https://github.com/Devansh-567/chronomap.git
```

This lets you pull in the latest changes from the main repo at any time.

---

## Project Structure

```
chronomap/
├── chronomap/
│   ├── __init__.py        # Package exports and version
│   ├── chronomap.py       # Core — ChronoMap, AsyncChronoMap, LRUCache, RWLock
│   ├── cli.py             # Command-line interface
│   └── __main__.py        # Entry point for python -m chronomap
│
├── tests/
│   └── test_chronomap.py  # All unit tests
│
├── examples/
│   ├── cache_manager.py
│   ├── config_version_control.py
│   ├── feature_flag.py
│   ├── metrics_collector.py
│   └── session_manager.py
│
├── CONTRIBUTING.md
├── README.md
├── LICENSE
└── pyproject.toml
```

`chronomap/chronomap.py` is where all the core logic lives — that's the main file you'll work with for most contributions.

---

## Making Changes

### Step 1 — Sync with upstream before starting

```bash
git fetch upstream
git checkout main
git merge upstream/main
```

### Step 2 — Create a branch

Never work directly on `main`. Use a descriptive branch name:

```bash
git checkout -b feature/get-or-set-method
git checkout -b fix/ttl-cache-invalidation
git checkout -b docs/lrucache-examples
git checkout -b test/cli-parse-value
```

### Step 3 — Write your code

A few things to keep in mind:

- **Match the existing style** — look at the code around what you're changing.
- **Add type hints** to all new methods.
- **Write a docstring** for every new public method, including `Args:`, `Returns:`, and an `Example:` block.
- **Keep methods focused** — one method should do one thing.

#### Docstring format

```python
def my_method(self, key: Any, count: int = 10) -> List[Any]:
    """
    One-line description of what this does.

    More detail if needed — edge cases, thread safety,
    or performance notes go here.

    Args:
        key: The key to operate on (must be hashable).
        count: How many results to return. Defaults to 10.

    Returns:
        A list of matching values.

    Raises:
        ChronoMapKeyError: If the key does not exist and strict=True.

    Example:
        >>> cm = ChronoMap()
        >>> cm.put('sensor', 42)
        >>> cm.my_method('sensor', count=5)
        [42]
    """
```

### Step 4 — Write tests

Every change needs tests. Add them to `tests/test_chronomap.py` inside the relevant class, or create a new class for a distinct feature.

```python
class TestMyFeature:

    def test_basic_case(self):
        cm = ChronoMap()
        cm['key'] = 'value'
        assert cm.my_method('key') == ['value']

    def test_missing_key_returns_empty(self):
        cm = ChronoMap()
        assert cm.my_method('nonexistent') == []

    def test_respects_count_limit(self):
        cm = ChronoMap()
        for i in range(20):
            cm.put('key', i, timestamp=float(i))
        assert len(cm.my_method('key', count=5)) == 5
```

---

## Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run a specific test class
pytest tests/test_chronomap.py::TestLRUCache -v

# Run a specific test
pytest tests/test_chronomap.py::TestLRUCache::test_lru_cache_basic -v

# Run with coverage
pytest tests/ --cov=chronomap --cov-report=term-missing

# Run async tests only
pytest tests/test_chronomap.py::TestAsyncChronoMap -v
```

Please make sure your changes do not decrease the overall coverage below 97%.

---

## Code Style

ChronoMap uses `black` for formatting and `flake8` for linting.

```bash
# Format
black chronomap/ tests/

# Lint
flake8 chronomap/ tests/ --max-line-length=100
```

Fix all warnings before opening a PR. Common ones to watch for:

- `E501` — line too long (keep under 100 characters)
- `F401` — unused import
- `E302` — missing blank lines before a class or function

---

## Submitting a Pull Request

### Checklist before opening your PR

- [ ] All existing tests pass (`pytest tests/ -v`)
- [ ] New tests are written for your changes
- [ ] Code is formatted with `black`
- [ ] No `flake8` warnings
- [ ] New public methods have docstrings
- [ ] PR is targeting the `main` branch

### PR title format

```
[Type] Short description

[Feature] Add get_or_set method with TTL support
[Fix]     TTL expiry not invalidating LRU cache
[Docs]    Add examples to LRUCache docstrings
[Test]    Add unit tests for CLI parse_value
[Perf]    Reduce lock contention in put_many
```

### PR description

Please include:

1. **What does this PR do?**
2. **Which issue does it close?** — write `Closes #42` to link it automatically.
3. **How to test it?** — paste the exact command to run your new tests.
4. **Any decisions or trade-offs?** — mention if you chose one approach over another.

### Example

```
## What
Adds `get_or_set(key, factory, ttl=None)` — returns the cached value if it
exists, otherwise calls factory() and stores the result.

## Closes
Closes #12

## Testing
pytest tests/test_chronomap.py::TestGetOrSet -v

## Notes
The factory is only called on a true cache miss (missing or expired key),
not on every invocation.
```

### After you submit

1. A maintainer will review your PR within a few days.
2. You may be asked to make changes — this is normal, not a rejection.
3. Push the changes to the same branch; the PR updates automatically.
4. Once approved it will be merged.

---

## Getting Help

- **Comment on the issue** you're working on — the maintainer will reply.
- **Open a GitHub Discussion** for general questions.
- **Email**: devansh.jay.singh@gmail.com

---

Thank you for contributing to ChronoMap. Every pull request — big or small — makes this project better. 🙌
