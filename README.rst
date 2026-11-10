Losant Python MQTT Client
=========================

|test-badge|_ |pypi-badge|_

.. |test-badge| image:: https://github.com/Losant/losant-mqtt-python/actions/workflows/test.yml/badge.svg?branch=master
.. _test-badge:  https://github.com/Losant/losant-mqtt-python/actions/workflows/test.yml

.. |pypi-badge| image:: https://badge.fury.io/py/losant-mqtt.svg
.. _pypi-badge: https://badge.fury.io/py/losant-mqtt

The `Losant <https://www.losant.com>`_ MQTT client provides a simple way for
custom things to communicate with the Losant platform over MQTT.  You can authenticate
as a device, publish device state, and listen for device commands.

This client requires Python 3.11 or newer. It uses the
`Paho MQTT Client <https://github.com/eclipse/paho.mqtt.python>`_ under the
covers for the actual MQTT communication.

How it works
------------

A ``Device`` is one MQTT connection to Losant and two topics.

::

     your code                 Device                       Losant broker
    -----------              ----------                    ---------------
    send_state(...)  ---->   publish    ---->  losant/<device_id>/state
    "command" event  <----   subscribe  <----  losant/<device_id>/command

                connect()                 CONNACK ok
     idle  ------------------->  connecting  ---------->  connected
      ^                              |                      |    |
      |                    refused   |                      |    | connection drops
      |             bad credentials: AuthError              |    v
      |             anything else: retry                    |  reconnecting
      |                                                     |    |
      +------------------ close() --------------------------+    +--> connected

Contributors and maintainers: `docs/ <https://github.com/Losant/losant-mqtt-python/blob/master/docs/index.md>`_ explains how the internals work.

Installation
------------

Requires Python 3.11 or newer. The latest stable version is available in the Python
Package Index (PyPI) and can be installed using

::

    pip install losant-mqtt

or, in a `uv <https://docs.astral.sh/uv/>`_ project:

::

    uv add losant-mqtt


Upgrading from 1.x
------------------

2.0 raises the Python floor, upgrades paho-mqtt, changes the license to Apache 2.0, and tightens
a few APIs. The connection behavior and wire format are unchanged.

* Python 3.11 or newer is required. Python 2.7 and 3.8 through 3.10 are no longer supported.
* paho-mqtt 2.x is used. If you also use paho directly, note that paho 2.x changed its callback API.
* ``secure`` and ``transport`` are keyword-only:

  ::

      Device(device_id, key, secret, False)          # 1.x
      Device(device_id, key, secret, secure=False)   # 2.0

* Bad credentials raise ``losantmqtt.AuthError``, a subclass of ``losantmqtt.LosantError`` and of
  ``Exception``, so an existing ``except Exception`` still catches it. It is raised from the
  network loop: out of ``connect`` when blocking, out of ``loop`` when not.
* ``loop()`` in blocking mode raises ``RuntimeError`` instead of a bare ``Exception``.
* ``UtcTzinfo`` and ``UTC`` are removed from ``losantmqtt.device``. Use ``datetime.timezone.utc``.
* Command dates are always timezone-aware UTC datetimes.
* In ``send_state``, naive datetimes are treated as UTC and ``struct_time`` values as local time.
  This is unchanged from 1.x, but now documented.

``add_event_observer``, ``remove_event_observer``, ``connect``, ``close``, ``send_state``,
``is_connected`` and the four events keep their names and behavior.

Development
-----------

This project uses `uv <https://docs.astral.sh/uv/>`_ to manage Python, the virtual environment,
and dependencies. You don't need to install Python 3.11+ yourself: uv downloads the version
pinned in ``.python-version`` if it isn't already available.

1. Install uv (see the `uv install docs <https://docs.astral.sh/uv/getting-started/installation/>`_):

   ::

       curl -LsSf https://astral.sh/uv/install.sh | sh    # or: brew install uv

2. Clone the repository and set up the environment. This creates ``.venv`` and installs the
   package, paho-mqtt, and the dev tools (ruff) at the versions in ``uv.lock``:

   ::

       git clone https://github.com/Losant/losant-mqtt-python.git
       cd losant-mqtt-python
       uv sync

3. Run the tests and the linter:

   ::

       uv run python -m unittest discover -s tests -p "*_tests.py"
       uv run ruff check .

``uv run`` always uses the project's environment, so there's nothing to activate. If you'd
rather work in a shell with the environment active, run ``source .venv/bin/activate``.

To try the client against a real device, put your device ID and credentials into
``examples/basic.py`` and run ``uv run python examples/basic.py``.

After changing dependencies in ``pyproject.toml``, run ``uv lock`` and commit the updated
``uv.lock``. There's more in `docs/development.md <https://github.com/Losant/losant-mqtt-python/blob/master/docs/development.md>`_.

Example
-------

Below is a high-level example of using the Losant Python MQTT client to send the value
of a temperature sensor to the Losant platform.

::

    import time
    from losantmqtt import AuthError, Device

    # Construct device
    device = Device("my-device-id", "my-app-access-key", "my-app-access-secret")

    def on_command(device, command):
        print("Command received.")
        print(command["name"])
        print(command["payload"])

    # Listen for commands.
    device.add_event_observer("command", on_command)

    # Connect to Losant.
    device.connect(blocking=False)

    # Send temperature once every second.
    try:
        while True:
            # loop() drives the network. Bad credentials raise AuthError from here.
            device.loop()
            if device.is_connected():
                temp = call_out_to_your_sensor_here()
                device.send_state({"temperature": temp})
            time.sleep(1)
    except AuthError as err:
        raise SystemExit(f"Could not authenticate: {err}")
    except KeyboardInterrupt:
        device.close()


API Documentation
-----------------

* `Device`_
    * `constructor`_
    * `connect`_
    * `is_connected`_
    * `close`_
    * `send_state`_
    * `loop`_
    * `add_event_observer`_
    * `remove_event_observer`_

Device
******

A device represents a single thing or widget that you'd like to connect to the Losant platform.
A single device can contain many different sensors or other attached peripherals.
Devices can either report state or respond to commands.

A device's state represents a snapshot of the device at some point in time.
If the device has a temperature sensor, it might report state every few seconds
with the temperature. If a device has a button, it might only report state when
the button is pressed. Devices can report state as often as needed by your specific application.

Commands instruct a device to take a specific action. Commands are defined as a
name and an optional payload. For example, if the device is a scrolling marquee,
the command might be "update text" and the payload would include the text to update.

constructor
```````````

::

    Device(device_id, key, secret, *, secure=True, transport="tcp")

The ``Device()`` constructor takes the following arguments:

device_id
    The device's ID. Obtained by first registering a device using the Losant platform.

key
    The Losant access key.

secret
    The Losant access secret.

secure
    If the client should connect to Losant over SSL - default is true.

transport
    Allowed values are "tcp" and "websockets". Defaults to "tcp", which is a raw TCP connection over
    ports 1883 (insecure) or 8883 (secure). When "websockets" is passed in, connects using MQTT over
    WebSockets, which uses either port 80 (insecure) or port 443 (secure).

Example
.......

::

    from losantmqtt import Device

    device = Device("my-device-id", "my-app-access-key", "my-app-access-secret")

connect
```````

::

    connect(blocking=True)

Connects the device to the Losant platform. Hook the connect event to know when a connection
has been successfully established.  Connect takes the following arguments:

blocking
    If the connect method should block or not.  True is the default, which means that the connect
    call will be a blocking call that will not return until the connection is closed or an error
    occurs - all interaction has to be done through the various event callbacks.  If blocking is
    set to False, the function will only block until the connection is kicked off - after that point
    you must run the network loop yourself, by calling the `loop`_ method periodically.

If Losant refuses the device's credentials, ``AuthError`` is raised from the network loop - out of
``connect`` when blocking, and out of `loop`_ when not.

is_connected
````````````

::

    is_connected()

Returns a boolean indicating whether or not the device is currently connected
to the Losant platform.

close
`````

::

    close()

Closes the device's connection to the Losant platform.

send_state
``````````

::

    send_state(state, time_like=None)

Sends a device state to the Losant platform. In many scenarios, device states will
change rapidly. For example a GPS device will report GPS coordinates once a second or
more. Because of this, sendState is typically the most invoked function. Any state
data sent to Losant is stored and made available in data visualization tools
and workflow triggers.

state
    The state to send as a Dict.

time_like
    When the state occurred - if None or not set, will default to now.

Example
.......

::

    device.send_state({ "voltage": read_analog_in() })

loop
`````

::

    loop(timeout=1)

Loops the network stack for the connection.  Only valid to call when connected in non-blocking mode.
Be sure to call this reasonably frequently when in that model to make sure the underlying
MQTT connection does not get timed out.

timeout
    Max time to block on the socket before continuing - defaults to 1 second.

add_event_observer
``````````````````

::

    add_event_observer(event_name, observer)

Adds an observer to listen for an event on this device.

event_name
    The event to listen for.  Possible events are: "connect" (the device has connected),
    "reconnect" (the device lost its connection and reconnected),
    "close" (the device's connection was closed), and
    "command" (the device has received a command from Losant).

observer
    Callback method to call when the given event fires.  The first argument for all callbacks
    will be the device instance.  Command callbacks have a second argument - the command
    received.


Example
.......

::

    def on_command(device, cmd):
        print(cmd["time"]) # time of the command
        print(cmd["name"]) # name of the command
        print(cmd["payload"]) # payload of the command

    device.add_event_observer("command", on_command)

remove_event_observer
`````````````````````

::

    remove_event_observer(event_name, observer)

Removes an observer from listening for an event on this device.

event_name
    The event to stop listening for.  Same events as `add_event_observer`_.

observer
    Callback method to remove.

License
-------

Copyright (c) 2026 SUSE

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
