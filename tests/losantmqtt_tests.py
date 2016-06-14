# pylint: disable=C0111,W0212,R0903,W0201,C0301,E0401
import unittest
import time
from losantmqtt import Device

class MqttMock(object):

    def __init__(self):
        self.publish_calls = []

    def publish(self, topic, payload):
        self.publish_calls.append([topic, payload])
        return 0

class MsgMock(object):
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
        mock = MsgMock('{"name":"start","payload":{"one":[2,3]},"time":{"$date":"2016-06-01T01:09:51.145Z"}}')
        self.device._cb_client_command(None, None, mock)
        self.assertEqual(self.cmd_msg["name"], "start")
        self.assertEqual(self.cmd_msg["payload"], {"one": [2, 3]})
        self.assertEqual(self.cmd_msg["time"].microsecond, 145000)
        self.assertAlmostEqual(time.mktime(self.cmd_msg["time"].utctimetuple()), 1464761391.0)
