# AGENTS.md

## Build/Lint/Test Commands

**Environment Setup:**
```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e .
```

**Testing:**
```bash
# Run all tests
python -m pytest tests/

# Run specific test
python -m pytest tests/test_deduplication.py -v

# Run with coverage
python -m pytest --cov=omega13 tests/
```

## Code Style Guidelines

**Imports:** Use absolute imports for local modules, group standard library imports first, then third-party, then local imports.

**Formatting:** Follow PEP 8 guidelines. Use 4 spaces for indentation, limit lines to 88 characters.

**Types:** Use Python type hints for function signatures and variables. Avoid runtime type checking.

**Naming:** Use snake_case for variables/functions, CamelCase for classes, UPPER_CASE for constants.

**Error Handling:** Use specific exception types, avoid bare except clauses. Log errors appropriately.

**Thread Safety:** JACK process() callback must be lock-free and non-blocking. Use queue.Queue for inter-thread communication.

**Conventional Commits:** Use feat:, fix:, refactor:, perf:, docs:, test:, chore: prefixes for commit messages.
