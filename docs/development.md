# Development

The project uses [uv](https://docs.astral.sh/uv/) to manage Python, the virtual environment, and dependencies. You don't need to install Python yourself: uv downloads the version pinned in `.python-version` if it isn't available.

## Set up

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh    # or: brew install uv
git clone https://github.com/Losant/losant-mqtt-python.git
cd losant-mqtt-python
uv sync          # creates .venv, installs the package, paho-mqtt, and ruff from uv.lock
```

`uv run` always uses the project's environment, so there is nothing to activate. To work in a shell with it active, run `source .venv/bin/activate`.

## Everyday commands

```bash
uv run python -m unittest discover -s tests -p "*_tests.py"   # tests
uv run ruff check .                                           # lint
uv run ruff check . --fix                                     # lint and apply safe fixes
uv build                                                      # sdist and wheel into dist/
```

How the tests are built is in [testing.md](./testing.md). What the build and CI check is in [packaging-and-ci.md](./packaging-and-ci.md).

## Changing dependencies

Edit `pyproject.toml`, then run `uv lock` and commit the updated `uv.lock`. CI installs with `uv sync --locked`, which fails if the lockfile is out of date.
