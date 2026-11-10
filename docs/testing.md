# Testing

The suite is `unittest`, in `tests/losantmqtt_tests.py`, and it never opens a network connection. That works because `Device` is a thin layer over paho: nearly everything it does happens in a handful of callbacks and helpers that can be called directly.

## How `Device` is exercised

- **Callbacks are called directly.** `_cb_client_connect`, `_cb_client_disconnect` and `_cb_client_command` are invoked with hand-built arguments. Build reason codes with paho's own converters rather than writing numbers by hand:

  ```python
  from paho.mqtt.client import (
      convert_connack_rc_to_reason_code,
      convert_disconnect_error_code_to_reason_code,
  )

  convert_connack_rc_to_reason_code(5)           # a refusal, as paho 2.x reports it
  convert_disconnect_error_code_to_reason_code(0)  # a clean disconnect
  ```

  This is deliberate. paho 2.x reports MQTT 3.1.1 refusals as MQTT 5 values (132 to 135), and using the converters keeps the tests honest if paho changes.
- **`_mqtt_client` is swapped for a mock.** `MqttMock` records `publish` calls and returns an object with `.rc = 0`, which is what `send_state` reads.
- **`_fire_event` is exercised through observers.** Tests register an observer, trigger the callback, and assert on what the observer saw.

## What is covered

| Area | Tests |
|---|---|
| Topics and constructor properties | `TestDevice` |
| Observers: add, remove, fire | `TestDevice` |
| `send_state` payload and every `time_like` type | `TestDevice`, `TestSendStateTime` |
| Commands: JSON decode, `$date`, `$undefined` | `TestDevice`, `TestExtJsonDecode` |
| Connect, reconnect, refusal, disconnect | `TestConnectionCallbacks` |
| Keyword-only constructor options | `TestSendStateTime` |

## What is not covered

Nothing here talks to the real broker, so TLS, the bundled `RootCA.crt`, and real reconnects are untested. To check authentication end to end, connect with credentials you know are wrong and confirm you get `AuthError`:

```python
from losantmqtt import AuthError, Device

device = Device("000000000000000000000000", "bad", "bad")
try:
    device.connect()
except AuthError as err:
    print(err)   # Invalid Losant credentials - error code 135
```

## Adding a test

1. Put it in the class for the area it covers, or add a class.
2. Name it for the behavior, such as `test_naive_datetime_is_utc`.
3. Prefer calling a callback with a paho reason code over mocking paho itself.
4. Run the suite and `uv run ruff check .`.
