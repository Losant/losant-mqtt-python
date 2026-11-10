"""Losant MQTT client."""

from importlib.metadata import PackageNotFoundError, version

from .device import AuthError, Device, LosantError

try:
    __version__ = version("losant-mqtt")
except PackageNotFoundError:  # running from a source tree that isn't installed
    __version__ = "0+unknown"

__all__ = ["AuthError", "Device", "LosantError", "__version__"]
