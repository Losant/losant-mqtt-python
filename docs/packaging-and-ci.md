# Packaging and CI

## Packaging

Everything is in `pyproject.toml`, with setuptools as the build backend. There is no `setup.py`.

- **Version** is `project.version`. `losantmqtt.__version__` reads it back from the installed metadata with `importlib.metadata`, so it is never edited in code.
- **Python floor** is `requires-python = ">=3.11"`.
- **License** is the SPDX expression `Apache-2.0` plus `license-files = ["LICENSE"]`. SPDX expressions need `setuptools>=77`, and they can't be combined with a `License ::` classifier, so there isn't one.
- **Package data** is declared under `tool.setuptools.package-data`: `RootCA.crt`, which secure connections verify against, and `py.typed`, which marks the package as typed. If either is missing from the wheel, the client breaks or type checkers lose the hints.
- **Dependencies** are `paho-mqtt>=2.0.0,<3`, locked in `uv.lock`. Dev tools (ruff) are in `dependency-groups.dev`.

Check what ships:

```bash
uv build
unzip -l dist/*.whl | grep -E "RootCA.crt|py.typed"
```

## CI

Three GitHub Actions workflows run on every pull request and on pushes to `master`. Third-party actions are pinned by commit SHA, with the tag in a comment above.

| Job | Workflow | What it checks |
|---|---|---|
| `test` | `test.yml` | The suite on Python 3.11, 3.12, 3.13 and 3.14, installed with `uv sync --locked` |
| `build` | `test.yml` | `uv build`, then that `RootCA.crt` is in the wheel, then a fresh install of the wheel can import `losantmqtt` and find the certificate |
| `lint` | `lint.yml` | `ruff check .` |

The `build` job exists because the failure it catches, a wheel without the certificate, only shows up after install, when tests running from the source tree still pass.

## Ruff

Rules are set in `pyproject.toml`: `E`, `F`, `I`, `UP`, `B`, `SIM`, with a line length of 100 and a Python 3.11 target. Fix what you can with `uv run ruff check . --fix`.

## Releasing

There is no publish automation yet. To cut a release:

1. Bump `project.version` in `pyproject.toml`.
2. Add a section to `CHANGELOG.md`.
3. Run `uv lock` so `uv.lock` records the new version.
4. Merge, then build and publish by hand.
