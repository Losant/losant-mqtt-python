# Losant Python MQTT Client Changelog

## Losant Python MQTT Client v2.0.0

### Changed

* Relicensed from MIT to Apache License 2.0.
* Upgraded paho-mqtt from 1.x to 2.x (`>=2.0.0,<3`), using the v2 callback API.
* Raised minimum supported Python version to 3.11.
* Migrated packaging from `setup.py` to `pyproject.toml` and uv.
* Replaced `pkg_resources` with `importlib.resources` for locating the root certificate.
* CI now tests Python 3.11 through 3.14 and verifies the built package.

* `Device` options `secure` and `transport` are now keyword-only.
* Invalid credentials raise `AuthError` (subclass of `LosantError`) instead of a bare `Exception`.
* `loop()` raises `RuntimeError` instead of a bare `Exception` when called in blocking mode.
* Command `$date` values are always timezone-aware UTC datetimes.
* Added type hints and a `py.typed` marker, `__all__` and `__version__`.
* Modernized internals: f-strings, `OSError`, and a stricter ruff configuration.

### Removed

* `UtcTzinfo` and `UTC` from `losantmqtt.device`; use `datetime.timezone.utc`.

* Dropped support for Python 2.7 and Python 3.8 through 3.10.

--
