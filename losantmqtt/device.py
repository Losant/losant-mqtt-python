"""
The MIT License (MIT)

Copyright (c) 2019 Losant IoT, Inc.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

"""
Losant MQTT Device module

Contains the Device class, used for connecting a
device to the Losant platform.
"""

import time
import datetime
import calendar
import json
import logging
import pkg_resources
import socket
# pylint: disable=E0401
from paho.mqtt import client as mqtt

LOGGER = logging.getLogger(__name__)
ROOT_CA_PATH = pkg_resources.resource_filename(__name__, "RootCA.crt")

class UtcTzinfo(datetime.tzinfo):
    """UTC tzinfo from https://docs.python.org/2.7/library/datetime.html#datetime.tzinfo"""
    ZERO = datetime.timedelta(0)

    def utcoffset(self, dt):
        return UTC.ZERO

    def tzname(self, dt):
        return "UTC"

    def dst(self, dt):
        return UTC.ZERO
UTC = UtcTzinfo()

def ext_json_decode(dct):
    """Deals with $date and $undefined extended json fields.
    Originally from https://github.com/mongodb/mongo-python-driver/blob/master/bson/json_util.py
    """
    # pylint: disable=R0912
    if "$date" in dct:
        dtm = dct["$date"]
        # Parse offset
        if dtm[-1] == "Z":
            dstr = dtm[:-1]
            offset = "Z"
        elif dtm[-3] == ":":
            # (+|-)HH:MM
            dstr = dtm[:-6]
            offset = dtm[-6:]
        elif dtm[-5] in ("+", "-"):
            # (+|-)HHMM
            dstr = dtm[:-5]
            offset = dtm[-5:]
        elif dtm[-3] in ("+", "-"):
            # (+|-)HH
            dstr = dtm[:-3]
            offset = dtm[-3:]
        else:
            dstr = dtm
            offset = ""

        aware = datetime.datetime.strptime(dstr, "%Y-%m-%dT%H:%M:%S.%f").replace(tzinfo=UTC)

        if not offset or offset == "Z":
            # UTC
            return aware
        else:
            if len(offset) == 6:
                hours, minutes = offset[1:].split(":")
                secs = (int(hours) * 3600 + int(minutes) * 60)
            elif len(offset) == 5:
                secs = (int(offset[1:3]) * 3600 + int(offset[3:]) * 60)
            elif len(offset) == 3:
                secs = int(offset[1:3]) * 3600
            if offset[0] == "-":
                secs *= -1
            return aware - datetime.timedelta(seconds=secs)
    if "$undefined" in dct:
        return None
    return dct

class Device(object):
    """
    Losant MQTT Device class

    Used to communicate as a particular device over MQTT to Losant
    and report device state and receive commands.
    """

    mqtt_endpoint = "broker.losant.com"

    def __init__(self, device_id, key, secret, secure=True, transport="tcp"):
        self._device_id = device_id
        self._key = key
        self._secret = secret
        self._secure = secure
        self._transport = transport

        self._mqtt_client = None
        self._observers = {}
        self._initial_connect = False
        self._looping = False

    def add_event_observer(self, event_name, observer):
        """ Add an observer callback to an event.

        Available events are: "connect", "reconnect", "close", and "command".
        """
        if event_name in self._observers:
            self._observers[event_name].append(observer)
        else:
            self._observers[event_name] = [observer]

    def remove_event_observer(self, event_name, observer):
        """ Remove an observer callback from an event."""
        if event_name in self._observers:
            self._observers[event_name].remove(observer)

    def is_connected(self):
        """ Returns if the client is currently connected to Losant """
        # pylint: disable=W0212
        return self._mqtt_client and self._mqtt_client._state == mqtt.mqtt_cs_connected

    def connect(self, blocking=True):
        """ Attempts to establish a connection to Losant.

        Will be blocking or non-blocking depending on the value of
        the 'blocking' argument.  When non-blocking, the 'loop' function
        must be called to perform network activity.
        """
        if self._mqtt_client:
            return

        self._looping = blocking
        self._initial_connect = True
        self._mqtt_client = mqtt.Client(self._device_id, transport=self._transport)
        self._mqtt_client.username_pw_set(self._key, self._secret)

        port = 80 if self._transport == "websockets" else 1883
        if self._secure:
            self._mqtt_client.tls_set(ROOT_CA_PATH)
            port = 443 if self._transport == "websockets" else 8883

        LOGGER.debug("Connecting to Losant as %s", self._device_id)
        self._mqtt_client.on_connect = self._cb_client_connect
        self._mqtt_client.on_disconnect = self._cb_client_disconnect
        self._mqtt_client.message_callback_add(self._command_topic(), self._cb_client_command)
        self._mqtt_client.connect(Device.mqtt_endpoint, port, 15)
        if self._looping:
            self._mqtt_client.loop_forever()

    def loop(self, timeout=1):
        """ Performs network activity when connected in non blocking mode """
        if self._looping:
            raise Exception("Connection in blocking mode, don't call loop")

        if self._mqtt_client:
            result = self._mqtt_client.loop(timeout)
            if result != mqtt.MQTT_ERR_SUCCESS:
                LOGGER.debug("Attempting another reconnect for %s...", self._device_id)
                self._wrapped_reconnect()


    def close(self):
        """ Closes the connection to Losant """
        if self._mqtt_client:
            self._mqtt_client.disconnect()

    def send_state(self, state, time_like=None):
        """ Reports the given state to Losant for this device """
        LOGGER.debug("Sending state for %s", self._device_id)
        if not self._mqtt_client:
            return False

        if isinstance(time_like, datetime.datetime):
            # getting utc tuple, and so use timegm
            seconds = calendar.timegm(time_like.utctimetuple())
            millis = time_like.microsecond / 1000
            time_like = int(seconds * 1000 + millis)
        if isinstance(time_like, time.struct_time):
            # don't know the timezone, assume it is local and use mktime
            time_like = int(time.mktime(time_like) * 1000)
        if not time_like:
            time_like = int(time.time() * 1000)

        payload = json.dumps({"time": time_like, "data": state}, sort_keys=True)
        result = self._mqtt_client.publish(self._state_topic(), payload)

        return mqtt.MQTT_ERR_SUCCESS == result


    # ============================================================
    # Private functions
    # ============================================================

    def _command_topic(self):
        return "losant/{0}/command".format(self._device_id)

    def _state_topic(self):
        return "losant/{0}/state".format(self._device_id)

    def _fire_event(self, event_name, data=None):
        if not event_name in self._observers:
            return
        for observer in self._observers[event_name]:
            if data is None:
                observer(self)
            else:
                observer(self, data)

    def _cb_client_connect(self, client, userdata, flags, response_code):
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

        if response_code in (1, 2, 4, 5):
            raise Exception("Invalid Losant credentials - error code {0}".format(response_code))
        else:
            LOGGER.debug("%s retrying connection", self._device_id)
            self._wrapped_reconnect()

    def _cb_client_disconnect(self, client, userdata, response_code):
        if not self._mqtt_client:
            return
        if response_code == mqtt.MQTT_ERR_SUCCESS: # intentional disconnect
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
        if hasattr(payload, "decode"):
            payload = payload.decode("utf-8")
        msg = json.loads(payload, object_hook=ext_json_decode)
        self._fire_event("command", msg)

    def _wrapped_reconnect(self):
        # no need to trigger a reconnect ourselves if loop_forever is active
        if not self._looping:
            try:
                self._mqtt_client.reconnect()
            except socket.error as err:
                LOGGER.debug("Reconnect attempt failed for %s due to %s", self._device_id, err)
