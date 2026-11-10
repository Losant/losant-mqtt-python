# pylint: disable=C0111,W0212,R0903,W0201,C0301,E0401
import calendar
import datetime
import json
import time
import unittest

from paho.mqtt.client import (
    convert_connack_rc_to_reason_code,
    convert_disconnect_error_code_to_reason_code,
)

from losantmqtt import AuthError, Device
from losantmqtt.device import ext_json_decode


class MqttMock:

    def __init__(self):
        self.publish_calls = []

    def publish(self, topic, payload):
        self.publish_calls.append([topic, payload])
        return type("Info", (), {"rc": 0})()

class MsgMock:
    def __init__(self, msg):
        self.payload = msg

class TestDevice(unittest.TestCase):

    def setUp(self):
        self.device = Device("device_id", "device_key", "device_secret")

    def test_correct_props(self):
        self.assertEqual(self.device._device_id, "device_id")
        self.assertEqual(self.device._key, "device_key")
        self.assertEqual(self.device._secret, "device_secret")
        self.assertEqual(self.device._secure, True)
        self.assertEqual(self.device._command_topic(), "losant/device_id/command")
        self.assertEqual(self.device._state_topic(), "losant/device_id/state")

    def test_add_remove_observer(self):
        self.event_fired = 0
        def on_event(device):
            self.assertEqual(device, self.device)
            self.event_fired += 1
        self.device.add_event_observer("test", on_event)
        self.device._fire_event("test")
        self.assertEqual(self.event_fired, 1)
        self.device.remove_event_observer("test", on_event)
        self.device._fire_event("test")
        self.assertEqual(self.event_fired, 1)

    def test_send_state(self):
        self.device._mqtt_client = MqttMock()
        calls = self.device._mqtt_client.publish_calls
        self.assertEqual(len(calls), 0)
        result = self.device.send_state({"one": "two"}, 1234)
        self.assertEqual(result, True)
        calls = self.device._mqtt_client.publish_calls
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], "losant/device_id/state")
        expected_payload = '{"data": {"one": "two"}, "time": 1234}'
        self.assertEqual(calls[0][1], expected_payload)

    def test_receive_command(self):
        self.cmd_msg = None
        def on_command(device, msg):
            self.assertEqual(device, self.device)
            self.cmd_msg = msg
        self.device.add_event_observer("command", on_command)
        mock = MsgMock(
            '{"name":"start","payload":{"one":[2,3]},"time":{"$date":"2016-06-01T01:09:51.145Z"}}'
        )
        self.device._cb_client_command(None, None, mock)
        self.assertEqual(self.cmd_msg["name"], "start")
        self.assertEqual(self.cmd_msg["payload"], {"one": [2, 3]})
        self.assertEqual(self.cmd_msg["time"].microsecond, 145000)
        self.assertEqual(calendar.timegm(self.cmd_msg["time"].utctimetuple()), 1464743391.0)


class TestConnectionCallbacks(unittest.TestCase):

    def setUp(self):
        self.device = Device("device_id", "device_key", "device_secret")
        self.device._mqtt_client = MqttMock()
        self.device._mqtt_client.subscribe = lambda topic: None
        self.events = []
        for name in ("connect", "reconnect", "close"):
            self.device.add_event_observer(name, lambda _, name=name: self.events.append(name))

    def test_connect_then_reconnect(self):
        self.device._initial_connect = True
        success = convert_connack_rc_to_reason_code(0)
        self.device._cb_client_connect(None, None, None, success, None)
        self.device._cb_client_connect(None, None, None, success, None)
        self.assertEqual(self.events, ["connect", "reconnect"])

    def test_bad_credentials_raise(self):
        for connack_rc in (1, 2, 4, 5):
            reason = convert_connack_rc_to_reason_code(connack_rc)
            with self.assertRaises(AuthError):
                self.device._cb_client_connect(None, None, None, reason, None)

    def test_server_unavailable_does_not_raise(self):
        self.device._looping = True # reconnect handled by paho's loop_forever
        reason = convert_connack_rc_to_reason_code(3)
        self.device._cb_client_connect(None, None, None, reason, None)
        self.assertEqual(self.events, [])

    def test_intentional_disconnect_fires_close(self):
        reason = convert_disconnect_error_code_to_reason_code(0)
        self.device._cb_client_disconnect(None, None, None, reason, None)
        self.assertEqual(self.events, ["close"])
        self.assertIsNone(self.device._mqtt_client)

    def test_abnormal_disconnect_keeps_client(self):
        self.device._looping = True
        reason = convert_disconnect_error_code_to_reason_code(1)
        self.device._cb_client_disconnect(None, None, None, reason, None)
        self.assertEqual(self.events, [])
        self.assertIsNotNone(self.device._mqtt_client)

    def test_is_connected_false_without_client(self):
        self.device._mqtt_client = None
        self.assertFalse(self.device.is_connected())


class TestExtJsonDecode(unittest.TestCase):

    def decode(self, date):
        return json.loads(json.dumps({"$date": date}), object_hook=ext_json_decode)

    def test_date_formats_resolve_to_same_utc_instant(self):
        expected = datetime.datetime(2016, 6, 1, 1, 9, 51, 145000, tzinfo=datetime.UTC)
        for date in (
            "2016-06-01T01:09:51.145Z",
            "2016-06-01T01:09:51.145",
            "2016-06-01T03:09:51.145+02:00",
            "2016-06-01T03:09:51.145+0200",
            "2016-05-31T20:09:51.145-05:00",
        ):
            with self.subTest(date=date):
                self.assertEqual(self.decode(date), expected)
                self.assertEqual(self.decode(date).utcoffset(), datetime.timedelta(0))

    def test_undefined_is_none(self):
        self.assertIsNone(json.loads('{"$undefined": true}', object_hook=ext_json_decode))


class TestSendStateTime(unittest.TestCase):

    def send(self, time_like):
        device = Device("device_id", "device_key", "device_secret")
        device._mqtt_client = MqttMock()
        device.send_state({}, time_like)
        return json.loads(device._mqtt_client.publish_calls[0][1])["time"]

    def test_aware_datetime(self):
        tz = datetime.timezone(datetime.timedelta(hours=2))
        self.assertEqual(self.send(datetime.datetime(2016, 6, 1, 3, 0, tzinfo=tz)), 1464742800000)

    def test_naive_datetime_is_utc(self):
        self.assertEqual(self.send(datetime.datetime(2016, 6, 1, 1, 0)), 1464742800000)

    def test_millis_passthrough(self):
        self.assertEqual(self.send(1234), 1234)

    def test_default_is_now(self):
        self.assertAlmostEqual(self.send(None), time.time() * 1000, delta=5000)

    def test_device_requires_keyword_options(self):
        with self.assertRaises(TypeError):
            Device("device_id", "device_key", "device_secret", False)
