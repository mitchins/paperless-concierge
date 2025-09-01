# Testing & Troubleshooting

This project uses `pytest` with `pytest-asyncio`. If you hit issues running async tests locally, use the checklist below.

## Quick Checklist

- Install dev dependencies: `pip install -e .[dev]`
- Verify async test environment: `python tests/verify_tests.py`
- Run the test suite: `pytest -v`
- Ensure `pytest-asyncio` is installed and enabled

## Details

### Verify async test environment

```bash
python tests/verify_tests.py
# or
make test-verify
```

### Required pytest config

`pyproject.toml` contains the relevant options:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

If you also have a `pytest.ini` in your workspace, remove it (it can conflict with `pyproject.toml`).

### Common fixes

1) Install/upgrade tooling:

```bash
pip install -e .[dev]
```

2) Run tests:

```bash
pytest -v
```

3) Format and lint (optional, but recommended):

```bash
pre-commit run --all-files
```
