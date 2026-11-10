# How it works

Everything lives in `losantmqtt/device.py`. A `Device` is one MQTT connection to `broker.losant.com` and two topics. Everything else is bookkeeping around that.

```
   your code                 Device                        Losant broker
  -----------              ----------                     ---------------
  send_state(...)  ---->   publish    ---->  losant/<device_id>/state
  on "command"     <----   subscribe  <----  losant/<device_id>/command
```

State goes out on the `state` topic. Commands come in on the `command` topic, and the `Device` turns each one into a `"command"` event for your observers.

## Ports

| `secure` | `transport` | Port |
|---|---|---|
| `True` (default) | `"tcp"` (default) | 8883 |
| `True` | `"websockets"` | 443 |
| `False` | `"tcp"` | 1883 |
| `False` | `"websockets"` | 80 |

Secure connections verify the broker against the bundled `RootCA.crt`. The keepalive is 15 seconds.

## The connection lifecycle

In the code: `connect()` builds the paho client and registers `_cb_client_connect`, `_cb_client_disconnect` and `_cb_client_command`. Those three callbacks and `_wrapped_reconnect` are the whole state machine.

```
              connect()                  CONNACK ok
   idle  ----------------->  connecting  ------------>  connected
    ^                            |                         |   |
    |                            | CONNACK refused         |   | connection drops
    |                            v                         |   v
    |                   credentials bad?                   |  reconnecting --+
    |                    yes -> AuthError                  |       |         |
    |                    no  -> retry                      |       +---------+
    |                                                      |        (back to connected)
    |                      close()                         |
    +------------------------------------------------------+
                  "close" event, client cleared
```

Events fire at these points:

| Event | When |
|---|---|
| `connect` | The first successful connection after `connect()` |
| `reconnect` | Every later successful connection after a drop |
| `close` | After `close()`, once the broker confirms the disconnect |
| `command` | A command arrived. Observers receive `(device, command)` |

After `close`, the client is cleared, so you can call `connect()` again.

## Who drives the network?

MQTT needs something to read and write the socket. `connect(blocking=...)` decides whether that something is you.

| | `connect()` (blocking) | `connect(blocking=False)` |
|---|---|---|
| Network I/O | Runs inside `connect()` until the device closes | Only happens when you call `loop()` |
| Reconnects | paho handles them | `loop()` reconnects when the connection drops |
| You must | Nothing, `connect()` doesn't return | Call `loop()` often enough to beat the 15 second keepalive |
| Calling `loop()` | Raises `RuntimeError` | Required |

## When the broker refuses you

Handled in `_cb_client_connect`; the set of fatal codes is `CREDENTIAL_ERROR_CODES`.

The broker answers a connection with a CONNACK. If it refuses, paho 2.x reports an MQTT 5 style reason code even though the connection speaks MQTT 3.1.1:

| Reason code | Meaning | What `Device` does |
|---|---|---|
| 132 | Unsupported protocol version | Raises `AuthError` |
| 133 | Client identifier not valid | Raises `AuthError` |
| 134 | Bad user name or password | Raises `AuthError` |
| 135 | Not authorized | Raises `AuthError` |
| 136 and others | Server unavailable, unspecified error | Retries |

Retrying a bad password never helps, so those four stop the client. The rest might be temporary.

### Where `AuthError` comes out

The CONNACK is handled inside the network loop, so that is where the exception surfaces:

- **Blocking:** out of `connect()`.
- **Non-blocking:** out of `loop()`. `connect(blocking=False)` returns before the broker has answered, so it cannot raise `AuthError`.

```python
device.connect(blocking=False)
try:
    while True:
        device.loop()
        time.sleep(1)
except AuthError:
    ...
```

## Commands

Commands arrive as JSON with a `name`, an optional `payload`, and a `time`. Losant encodes some values in extended JSON, and the client decodes two of them:

| JSON | Python |
|---|---|
| `{"$date": "2016-06-01T01:09:51.145Z"}` | A timezone-aware `datetime` in UTC |
| `{"$undefined": true}` | `None` |

Dates with an offset, such as `+02:00`, are converted to the same UTC instant. A date with no offset is read as UTC.
