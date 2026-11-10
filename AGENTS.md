# AGENTS.md

Guidance for AI coding agents working in this repository.

## Project overview

`losant-mqtt` is the Python MQTT client for the Losant platform. It wraps paho-mqtt in a `Device` class that connects as a device, publishes state, and receives commands. The package is `losantmqtt`, and the whole implementation is in `losantmqtt/device.py`. Read `README.rst` for the public API. `docs/` is for maintainers and agents: it explains how the internals work, how the tests are built, and how packaging and CI fit together.

## Setup commands

```bash
uv sync
```

## Testing instructions

- Tests: `uv run python -m unittest discover -s tests -p "*_tests.py"`
- Lint: `uv run ruff check .`
- Build: `uv build`, then check that `RootCA.crt` is in the wheel.
- Tests never touch the network. Test `Device` by calling its `_cb_client_*` callbacks directly, using paho's `convert_connack_rc_to_reason_code` and `convert_disconnect_error_code_to_reason_code` to build reason codes.
- Run lint and tests before every commit.

## Code style

- Python 3.11+. Use type hints, f-strings, and `datetime.timezone.utc`.
- Ruff enforces the rules in `pyproject.toml`, with a line length of 100.
- Keep the public surface small. Anything exported from `losantmqtt/__init__.py` is public API and needs a `CHANGELOG.md` entry when it changes.
- Raise `LosantError` subclasses, never a bare `Exception`.

## Gotchas

- **paho 2.x reports MQTT 3.1.1 refusals as MQTT 5 reason code values.** Bad credentials arrive as 132 to 135, not the old 1, 2, 4, 5. `CREDENTIAL_ERROR_CODES` holds them. Never compare `reason_code.value` against the old numbers.
- **`AuthError` surfaces from the network loop.** That is `connect()` when blocking and `loop()` when not. `connect(blocking=False)` cannot raise it.
- **Naive datetimes are UTC, `struct_time` is local time.** `send_state` has always worked this way. Changing it is a breaking change.
- **`RootCA.crt` and `py.typed` must stay in the wheel.** They are listed under `tool.setuptools.package-data` in `pyproject.toml`.
- **Do not hand-edit `uv.lock`.** Run `uv lock`.

## Docs

- `docs/index.md` lists the deeper docs.
- `docs/` describes how the code works, not how to use it. When internals change, update the matching file there. When public behavior changes, update `README.rst` and `CHANGELOG.md` too.

## PR instructions

- Commit messages are Conventional Commits, one terse line.
- Breaking changes use `feat!:` or `fix!:` and need an entry in `CHANGELOG.md` and a bullet in the README's "Upgrading" section.
