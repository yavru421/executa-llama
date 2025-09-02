# Contributing Guide

Thanks for your interest in improving PiControl Agent!

## Quick Start
1. Fork & clone the repo.
2. Create a branch: `git checkout -b feature/my-change`.
3. Create a virtual environment & install deps: `pip install -r requirements.txt`.
4. Run tests: `pytest -q`.
5. Make changes (add tests for new logic / tools).
6. Ensure `pytest` passes and no obvious lint errors (Black/Flake8 optional future).
7. Commit using conventional commits (e.g. `feat: add gpio toggle tool`).
8. Open a Pull Request and fill out the description template.

## Adding a Plugin Tool
- Place a new Python file in `llamatrama_agent/plugins/`.
- Expose one or more functions with clear docstrings (inputs / outputs / side effects).
- Keep network or long-running operations minimal; stream output if future streaming is added.
- Add at least one test demonstrating use (or mock the SSH layer where applicable).

## Tests
- Core tests live under `tests/`.
- If adding SSH behavior, mock network side effects.
- Prefer small, deterministic tests.

## Documentation
- Update `README.md` if user-facing behavior changes.
- Add examples where helpful.

## Style
- Python 3.12+
- Aim for clarity over cleverness.

## Code of Conduct
Participation is governed by `CODE_OF_CONDUCT.md`.

## License
By contributing you agree your work is licensed under the MIT License.
