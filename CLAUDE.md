## Type checking

This project uses ty for type checking. Always invoke through `uv run`. When working with types or migrating from mypy or pyright, invoke `/astral:ty` to follow OpenAI's recommended usage.

- Check the whole project: `uv run ty check`
- Check a single path: `uv run ty check src/model`
- Configuration lives in `pyproject.toml` under `[tool.ty]`.
