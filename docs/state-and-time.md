# State and time

`Device.send_state(state, time_like=None)` publishes one message to `losant/<device_id>/state`:

```json
{"data": {"temperature": 21.5}, "time": 1464742800000}
```

`data` is your dict. `time` is when the state happened, in milliseconds since the Unix epoch. `time_like` is the one argument that needs interpreting:

| You pass | Interpreted as |
|---|---|
| Nothing, or `None` | Now |
| An `int` or `float` | Milliseconds since the epoch, sent as given |
| A timezone-aware `datetime` | That instant |
| A naive `datetime` | UTC |
| A `time.struct_time` | Local time, converted with `time.mktime` |

The naive `datetime` and `struct_time` rows disagree, and that is deliberate: it is how 1.x behaved, so changing either is a breaking change. The `datetime` branch uses `calendar.timegm(utctimetuple())`, which reads a naive value as UTC; the `struct_time` branch uses `time.mktime`, which reads it as local time. Callers who are unsure should pass an aware `datetime`:

```python
from datetime import datetime, timezone

device.send_state({"temperature": 21.5}, datetime.now(timezone.utc))
```

`send_state` returns `True` if the publish was accepted, and `False` if the device has no connection yet. It does not wait for the broker to acknowledge the message.
