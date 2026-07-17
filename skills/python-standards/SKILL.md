---
name: python-standards
description: "Jacob's house standard for Python repos: uv-managed single pyproject.toml, ruff, basedpyright, pytest with a coverage ratchet, pre-commit hooks, and the .env convention. Use when setting up or standardizing a Python repo, adding lint/type-check/test tooling, wiring pre-commit, writing or reviewing tests, or deciding how a Python project should be configured."
---

# Python house standard

Every Python repo lands on the same setup: uv-managed, one `pyproject.toml`
holding all dependencies and tool config, ruff + basedpyright + pytest gated
by pre-commit, zero custom setup steps. This skill is the reference for that
standard — copy the templates, don't improvise variants.

## Target state (definition of done)

- [ ] `.python-version` pins `3.11`; `requires-python = ">=3.11"`
- [ ] One `pyproject.toml` declares everything: runtime deps, dev deps in
      `[dependency-groups]`, and all tool config (ruff, basedpyright, pytest,
      coverage). No `requirements*.txt`, `setup.py`, `setup.cfg`, `Pipfile`,
      or custom setup scripts remain.
- [ ] `uv.lock` committed; `uv sync` succeeds from a fresh clone with no
      manual steps
- [ ] Pre-commit installed: hygiene hooks, ruff format + lint, uv-lock,
      basedpyright, unit pytest with the coverage ratchet
- [ ] `.env.example` committed; real env files gitignored
- [ ] Every entry point runs as a single `uv run` command, listed in a
      README "Running" table: `| command | what it does |`

## uv rules

- Never `pip install` anything. Never write or keep a setup shell script.
  Every dependency or build fix lands in `pyproject.toml`
  (`[tool.uv.extra-build-dependencies]` for undeclared build deps).
- Python 3.11 only (`uv python pin 3.11`). Do not "helpfully" upgrade.
- Standalone scripts are single files with a PEP 723 `# /// script` header,
  runnable anywhere via `uv run script.py` with no environment setup.
- If a fix genuinely requires an environment variable (proxy, CA bundle), it
  goes in `.env.example` with a comment — never left as undocumented shell
  state. `uv sync` does not read `.env`; export first:
  `set -a; source .env; set +a`.
- Verify from zero before calling setup done:
  `rm -rf .venv && uv sync && uv run python -c "import <pkg>"`.

## pyproject.toml templates

Copy these blocks; adjust only where a comment says to.

### ruff

Rule families chosen to catch real bugs without style-cop noise:

```toml
[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = [
    "E4", "E7", "E9", # pycodestyle errors (subset that matters with a formatter)
    "F",              # pyflakes — undefined names, unused imports/vars
    "I",              # isort — deterministic import order
    "UP",             # pyupgrade — modern 3.11 idioms
    "B",              # bugbear — likely bugs (mutable defaults, etc.)
    "SIM",            # simplify — collapsible ifs, redundant bools
    "C4",             # comprehension rewrites
    "RUF",            # ruff-specific correctness checks
]

[tool.ruff.lint.per-file-ignores]
# Add brownfield hotspots here file-by-file; never delete a family above
# to silence one module.
```

Never weaken global lint/type config to silence one file — per-file-ignores
only, and the global bar stays where it is.

### basedpyright

`basic` for brownfield — basedpyright's default ("recommended") is stricter
than pyright strict and buries untyped code in thousands of findings.
Greenfield repos start at `recommended`. Ratchet upward
(`basic` → `standard` → `recommended`) in dedicated commits once clean.

```toml
[tool.basedpyright]
pythonVersion = "3.11"
venvPath = "."
venv = ".venv"
typeCheckingMode = "basic"   # ADJUST: "recommended" for greenfield
exclude = [".venv"]
```

When fixing type errors: pure type-domain edits only (annotations, stubs via
`uv add --dev types-*`, `TYPE_CHECKING` imports, `Protocol`/`overload`).
Never add asserts, None-guards, or isinstance checks just to satisfy the
checker — those change runtime behavior. Suppress with
`# pyright: ignore[specificRule]` (always with the rule in brackets, never
bare) and flag real bugs for a separate pass.

### pytest + coverage

```toml
[tool.pytest.ini_options]
minversion = "8.0"
testpaths = ["tests"]
addopts = ["-ra", "--strict-markers", "--strict-config", "--import-mode=importlib"]
xfail_strict = true
filterwarnings = ["error"]
markers = [
    "integration: touches a real DB/network/container; excluded from pre-commit, run with `uv run pytest -m integration`",
]

[tool.coverage.run]
branch = true
source = ["src"]          # ADJUST if the repo doesn't use src/ layout

[tool.coverage.report]
fail_under = 0            # ADJUST: the ratchet — see below
skip_covered = true
show_missing = true
```

`filterwarnings = ["error"]` makes deprecation rot a test failure instead of
scroll-by noise; if a third-party warning is genuinely unfixable, add a
targeted `"ignore:<msg>:<category>:<module>"` entry — never delete `"error"`.
Async repos add `asyncio_mode = "auto"` after `uv add --dev pytest-asyncio`.

**The coverage ratchet:** `fail_under` starts at current measured branch
coverage rounded down, and only ever increases. Coverage is a map of what's
untested, not a target — never write a test whose only purpose is moving the
percentage. ~85% is a healthy plateau; 100% is not a goal.

## Pre-commit

Basedpyright and pytest run as **local** hooks via `uv run` — published
type-checker hooks run in an isolated environment without the project's
dependencies and produce bogus import errors. Cheap checks first. The `rev:`
pins go stale — run `uv run pre-commit autoupdate` right after copying.

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-toml
      - id: check-added-large-files
      - id: check-merge-conflict
      - id: detect-private-key

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.12.5
    hooks:
      - id: ruff-check
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/astral-sh/uv-pre-commit
    rev: 0.8.4
    hooks:
      - id: uv-lock   # fails the commit if pyproject.toml changed without uv.lock

  - repo: local
    hooks:
      - id: basedpyright
        name: basedpyright
        entry: uv run basedpyright
        language: system
        types: [python]
        pass_filenames: false
      - id: pytest
        name: pytest (unit, with coverage ratchet)
        entry: uv run pytest -m "not integration" --cov -q
        language: system
        pass_filenames: false
        types: [python]
```

Install:

```bash
uv add --dev ruff basedpyright pre-commit pytest pytest-cov pytest-randomly pytest-mock
uv run pre-commit install
uv run pre-commit run --all-files
```

The full unit suite runs on every commit — that's the house trade-off, and
it's why unit tests must stay in the milliseconds and everything slow goes
behind the `integration` marker. If the hook creeps past ~30 seconds, find
the slow tests (`uv run pytest --durations=10`) and move or fix them — not
`--no-verify`, not removing the hook.

## .env convention

- `.env.example` — committed. Every variable the code reads, placeholder
  values, one comment per var.
- One real file per environment (`.env.dev`, `.env.staging`, `.env.prod`),
  all gitignored. `.env` is a symlink to the active one: `ln -sf .env.dev .env`.
- Commands load it explicitly: `uv run --env-file .env ...`. Code reads
  `os.environ` only — no `load_dotenv()`, no dotenv dependency.

```gitignore
.env
.env.*
!.env.example
```

## Testing standard

The reader of every test is someone who does NOT know testing jargon.

1. **Every test must be able to fail** — name the plausible bug it catches
   before writing it. Kills getter tests and mock-echo tests.
2. **Expected values come from the spec or docstring, never from running the
   code and pasting its output.** Unclear expected behavior → ask; the
   answer becomes the docstring AND the test.
3. **Test names are behavior sentences**: `test_expired_token_is_rejected`,
   never `test_process_2`.
4. **One behavior per test.** Arrange-Act-Assert with blank lines between
   blocks; plain `assert`. Duplicate setup beats clever shared abstractions.
5. **Assert on results and state, not on calls.** `assert_called_once_with`
   as the only assertion is banned, except when the call IS the behavior —
   then assert against a hand-written fake's recorded state.
6. **Mocking ladder — highest rung available:** real thing (`tmp_path`,
   in-memory DB for that DB's code) → hand-written fake of a boundary module
   you own → `mocker`/`monkeypatch` as last resort.
7. **Never mock what you don't own** (`httpx`, `oracledb`, `pandas`
   internals). Wrap the external thing in a thin gateway module and fake
   the gateway. Pass dependencies as parameters instead of patching import
   paths — if you're reaching for `mocker.patch`, refactor first.
8. **Anything touching network/DB/containers/real filesystem** goes behind
   the `integration` marker so the pre-commit unit run stays fast.

If logic and I/O are tangled (SQL/HTTP mid-function), extract pure functions
and push I/O to a gateway at the edge before testing — most tests should
need no test doubles at all.

## Improving this skill

Before executing, read `LEARNINGS.md` in this skill's folder — entries there
override the instructions above. After use, if the user corrected you or the
outcome surprised you, append one dated line to `LEARNINGS.md`:
`- YYYY-MM-DD: <what happened> → <what to do instead>`. Do not edit SKILL.md
directly; lessons are folded in deliberately, not on the fly.
