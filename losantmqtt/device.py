"""
Losant MQTT Device module

Contains the Device class, used for connecting a
device to the Losant platform.
"""

from __future__ import annotations

import calendar
import datetime
import json
import logging
import time
from collections.abc import Callable
from importlib import resources
from typing import Any, Literal

from paho.mqtt import client as mqtt

LOGGER = logging.getLogger(__name__)

# paho 2.x reports MQTT 3.1.1 CONNACK refusals with MQTT 5 reason code values.
# These are the refusals that mean the credentials are bad and retrying is pointless:
# unsupported protocol version, client id not valid, bad user name or password,
# and not authorized (previously CONNACK return codes 1, 2, 4 and 5).
CREDENTIAL_ERROR_CODES = (132, 133, 134, 135)
ROOT_CA_PATH = str(resources.files(__package__) / "RootCA.crt")

Observer = Callable[..., None]


class LosantError(Exception):
    """Base class for errors raised by this package."""


class AuthError(LosantError):
    """Raised when Losant refuses the device credentials."""


def ext_json_decode(dct: dict[str, Any]) -> Any:
    """Deals with $date and $undefined extended json fields.

    Dates are returned as timezone-aware UTC datetimes.
    """
    if "$date" in dct:
        parsed = datetime.datetime.fromisoformat(dct["$date"])
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=datetime.UTC)
        return parsed.astimezone(datetime.UTC)
    if "$undefined" in dct:
        return None
    return dct


class Device:
    """
    Losant MQTT Device class

    Used to communicate as a particular device over MQTT to Losant
    and report device state and receive commands.
    """

    mqtt_endpoint = "broker.losant.com"

    def __init__(
        self,
        device_id: str,
        key: str,
        secret: str,
        *,
        secure: bool = True,
        transport: Literal["tcp", "websockets"] = "tcp",
    ) -> None:
        self._device_id = device_id
        self._key = key
        self._secret = secret
        self._secure = secure
        self._transport = transport

        self._mqtt_client: mqtt.Client | None = None
        self._observers: dict[str, list[Observer]] = {}
        self._initial_connect = False
        self._looping = False

    def add_event_observer(self, event_name: str, observer: Observer) -> None:
        """ Add an observer callback to an event.

        Available events are: "connect", "reconnect", "close", and "command".
        """
        self._observers.setdefault(event_name, []).append(observer)

    def remove_event_observer(self, event_name: str, observer: Observer) -> None:
        """ Remove an observer callback from an event."""
        if event_name in self._observers:
            self._observers[event_name].remove(observer)

    def is_connected(self) -> bool:
        """ Returns if the client is currently connected to Losant """
        return bool(self._mqtt_client and self._mqtt_client.is_connected())

    def connect(self, blocking: bool = True) -> None:
        """ Attempts to establish a connection to Losant.

        Will be blocking or non-blocking depending on the value of
        the 'blocking' argument.  When non-blocking, the 'loop' function
        must be called to perform network activity.

        Raises AuthError if Losant refuses the credentials.
        """
        if self._mqtt_client:
            return

        self._looping = blocking
        self._initial_connect = True
        client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=self._device_id,
            transport=self._transport,
        )
        self._mqtt_client = client
        client.username_pw_set(self._key, self._secret)

        port = 80 if self._transport == "websockets" else 1883
        if self._secure:
            client.tls_set(ROOT_CA_PATH)
            port = 443 if self._transport == "websockets" else 8883

        LOGGER.debug("Connecting to Losant as %s", self._device_id)
        client.on_connect = self._cb_client_connect
        client.on_disconnect = self._cb_client_disconnect
        client.message_callback_add(self._command_topic(), self._cb_client_command)
        client.connect(Device.mqtt_endpoint, port, 15)
        if self._looping:
            client.loop_forever()

    def loop(self, timeout: float = 1) -> None:
        """ Performs network activity when connected in non blocking mode """
        if self._looping:
            raise RuntimeError("Connection in blocking mode, don't call loop")

        if self._mqtt_client:
            result = self._mqtt_client.loop(timeout)
            if result != mqtt.MQTT_ERR_SUCCESS:
                LOGGER.debug("Attempting another reconnect for %s...", self._device_id)
                self._wrapped_reconnect()

    def close(self) -> None:
        """ Closes the connection to Losant """
        if self._mqtt_client:
            self._mqtt_client.disconnect()

    def send_state(
        self,
        state: dict[str, Any],
        time_like: datetime.datetime | time.struct_time | int | float | None = None,
    ) -> bool:
        """ Reports the given state to Losant for this device.

        time_like is when the state occurred: a datetime, a struct_time, or
        milliseconds since the epoch. Naive datetimes are treated as UTC and
        struct_times as local time. If not set, defaults to now.
        """
        LOGGER.debug("Sending state for %s", self._device_id)
        if not self._mqtt_client:
            return False

        if isinstance(time_like, datetime.datetime):
            # utctimetuple treats naive datetimes as UTC, so use timegm
            seconds = calendar.timegm(time_like.utctimetuple())
            millis = time_like.microsecond / 1000
            time_like = int(seconds * 1000 + millis)
        elif isinstance(time_like, time.struct_time):
            # no timezone info, assume local and use mktime
            time_like = int(time.mktime(time_like) * 1000)
        if not time_like:
            time_like = int(time.time() * 1000)

        payload = json.dumps({"time": time_like, "data": state}, sort_keys=True)
        result = self._mqtt_client.publish(self._state_topic(), payload)

        return result.rc == mqtt.MQTT_ERR_SUCCESS

    # ============================================================
    # Private functions
    # ============================================================

    def _command_topic(self) -> str:
        return f"losant/{self._device_id}/command"

    def _state_topic(self) -> str:
        return f"losant/{self._device_id}/state"

    def _fire_event(self, event_name: str, data: Any = None) -> None:
        for observer in self._observers.get(event_name, []):
            if data is None:
                observer(self)
            else:
                observer(self, data)

    def _cb_client_connect(self, client, userdata, flags, reason_code, properties=None):
        response_code = reason_code.value
        if response_code == 0:
            self._mqtt_client.subscribe(self._command_topic())
            if self._initial_connect:
                self._initial_connect = False
                LOGGER.debug("%s successfully connected", self._device_id)
                self._fire_event("connect")
            else:
                LOGGER.debug("%s successfully reconnected", self._device_id)
                self._fire_event("reconnect")
            return

        LOGGER.debug("%s failed to connect, with mqtt error %s", self._device_id, response_code)

        if response_code in CREDENTIAL_ERROR_CODES:
            raise AuthError(f"Invalid Losant credentials - error code {response_code}")
        LOGGER.debug("%s retrying connection", self._device_id)
        self._wrapped_reconnect()

    def _cb_client_disconnect(
        self, client, userdata, disconnect_flags, reason_code, properties=None
    ):
        if not self._mqtt_client:
            return
        if reason_code.value == mqtt.MQTT_ERR_SUCCESS:  # intentional disconnect
            self._mqtt_client = None
            LOGGER.debug("Connection closed for %s", self._device_id)
            self._fire_event("close")
        else:
            LOGGER.debug("Connection abnormally ended for %s, reconnecting...", self._device_id)
            self._wrapped_reconnect()

    def _cb_client_command(self, client, userdata, msg):
        LOGGER.debug("Received command for %s", self._device_id)
        payload = msg.payload
        if not payload:
            return
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8")
        command = json.loads(payload, object_hook=ext_json_decode)
        self._fire_event("command", command)

    def _wrapped_reconnect(self) -> None:
        # no need to trigger a reconnect ourselves if loop_forever is active
        if not self._looping:
            try:
                self._mqtt_client.reconnect()
            except OSError as err:
                LOGGER.debug("Reconnect attempt failed for %s due to %s", self._device_id, err)
