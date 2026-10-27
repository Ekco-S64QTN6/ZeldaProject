# ZeldaProject dev commands.  (Use `make` equivalents if you prefer.)

default:
    @just --list

# Show available commands
help:
    @just --list

# Install in editable mode with dev deps
install:
    uv sync --extra dev

# Run the CLI
run *args:
    uv run zelda-suite {{args}}

# Check toolchain and ROM presence
doctor:
    uv run zelda-suite doctor

# Run tests
test:
    uv run pytest -q

# Lint + typecheck
check:
    uv run ruff check src tests
    uv run mypy src

# One-shot clean
clean:
    rm -rf .venv build dist **/__pycache__ .pytest_cache .ruff_cache .mypy_cache
