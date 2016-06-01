import time
import datetime
import json
import logging
import pkg_resources
from paho.mqtt import client as mqtt

logger = logging.getLogger(__name__)
root_ca_path = pkg_resources.resource_filename(__name__, "RootCA.crt")

class UTC(datetime.tzinfo):
    """UTC tzinfo from https://docs.python.org/2.7/library/datetime.html#datetime.tzinfo"""
    ZERO = datetime.timedelta(0)

    def utcoffset(self, dt):
        return UTC.ZERO

    def tzname(self, dt):
        return "UTC"

    def dst(self, dt):
        return UTC.ZERO
utc = UTC()

def ext_json_decode(dct):
    """Deals with $date and $undefined ext json options.  Originally from
    https://github.com/mongodb/mongo-python-driver/blob/master/bson/json_util.py
    """
    if "$date" in dct:
        dtm = dct["$date"]
        # Parse offset
        if dtm[-1] == 'Z':
            dt = dtm[:-1]
            offset = 'Z'
        elif dtm[-3] == ':':
            # (+|-)HH:MM
            dt = dtm[:-6]
            offset = dtm[-6:]
        elif dtm[-5] in ('+', '-'):
            # (+|-)HHMM
            dt = dtm[:-5]
            offset = dtm[-5:]
        elif dtm[-3] in ('+', '-'):
            # (+|-)HH
            dt = dtm[:-3]
            offset = dtm[-3:]
        else:
            dt = dtm
            offset = ''

        aware = datetime.datetime.strptime(dt, "%Y-%m-%dT%H:%M:%S.%f").replace(tzinfo=utc)

        if not offset or offset == 'Z':
            # UTC
            return aware
        else:
            if len(offset) == 6:
                hours, minutes = offset[1:].split(':')
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
    mqtt_endpoint = "broker.losant.com"

    def __init__(self, id, key, secret, secure=True):
        self._id = id
        self._key = key
        self._secret = secret
        self._secure = secure
        self._command_topic = "losant/{0}/command".format(self._id)
        self._state_topic = "losant/{0}/state".format(self._id)
        self._mqtt_client = None
        self._observers = { }
        self._initial_connect = False

    def add_event_observer(self, event_name, observer):
        if event_name in self._observers:
            self._observers[event_name].append(observer)
        else:
            self._observers[event_name] = [observer]

    def remove_event_observer(self, event_name, observer):
        if event_name in self._observers:
            self._observers[event_name].remove(observer)

    def is_connected(self):
        return self._mqtt_client._state == mqtt.mqtt_cs_connected

    def connect(self, blocking=True):
        if self._mqtt_client:
            return

        self._initial_connect = True
        self._mqtt_client = mqtt.Client(self._id)
        self._mqtt_client.username_pw_set(self._key, self._secret)

        port = 1883
        if self._secure:
            self._mqtt_client.tls_set(root_ca_path)
            port = 8883

        logger.debug("Connecting to Losant as %s", self._id)
        self._mqtt_client.on_connect = self._client_connect
        self._mqtt_client.on_disconnect = self._client_disconnect
        self._mqtt_client.message_callback_add(self._command_topic, self._client_command)
        self._mqtt_client.connect(Device.mqtt_endpoint, port, 15)
        if blocking:
            self._mqtt_client.loop_forever()

    def loop(self, timeout=1):
        if self._mqtt_client:
            self._mqtt_client.loop(timeout)

    def close(self):
        if self._mqtt_client:
            self._mqtt_client.disconnect()

    def send_state(self, state, time_like=None):
        logger.debug("Sending state for %s", self._id)
        if not self._mqtt_client:
            return False
        if not time_like:
            time_like = int(time.time() * 1000)
        if isinstance(time_like, datetime.datetime):
            time_like = int((time.mktime(time_like.utctimetuple()) * 1000) + (time_like.microsecond / 1000))
        if isinstance(time_like, time.struct_time):
            time_like = int(time.mktime(time_like) * 1000)

        payload = json.dumps({ "time": time_like, "data": state }, sort_keys=True)
        result = self._mqtt_client.publish(self._state_topic, payload)

        return mqtt.MQTT_ERR_SUCCESS == result


    # ============================================================
    # Private functions
    # ============================================================

    def _fire_event(self, event_name, data=None):
        if not event_name in self._observers:
            return
        for observer in self._observers[event_name]:
            if data == None:
                observer(self)
            else:
                observer(self, data)

    def _client_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self._mqtt_client.subscribe(self._command_topic)
            if self._initial_connect:
                self._initial_connect = False
                logger.debug("%s sucessfully connected", self._id)
                self._fire_event("connect")
            else:
                logger.debug("%s sucessfully reconnected", self._id)
                self._fire_event("reconnect")
            return

        logger.debug("%s failed to connect, with mqtt error %s", self._id, rc)

        if rc == 1 or rc == 2 or rc == 4 or rc == 5:
            raise Exception("Invalid Losant credentials - MQTT error code {0}".format(rc))
        else:
            logger.debug("%s retrying connection", self._id)
            self._mqtt_client.reconnect()

    def _client_disconnect(self, client, userdata, rc):
        if not self._mqtt_client:
            return
        if rc == mqtt.MQTT_ERR_SUCCESS: # intentional disconnect
            self._mqtt_client = None
            logger.debug("Connection closed for %s", self._id)
            self._fire_event("close")
        else:
            logger.debug("Connection abnormally terminated for %s, reconnecting...", self._id)
            self._mqtt_client.reconnect()

    def _client_command(self, client, userdata, msg):
        logger.debug('Received command for %s', self._id)
        payload = msg.payload.decode('utf-8')
        msg = json.loads(payload, object_hook=ext_json_decode)
        self._fire_event("command", msg)
