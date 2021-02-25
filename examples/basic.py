"""
The MIT License (MIT)

Copyright (c) 2021 Losant IoT, Inc.

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

import time
import random
from losantmqtt import Device

# Construct device
device = Device("my-device-id", "my-app-access-key", "my-app-access-secret")

def on_command(my_device, command):
    print("Command received.")
    print(command["name"])
    print(command["payload"])

# Listen for commands.
device.add_event_observer("command", on_command)

# Connect to Losant.
device.connect(blocking=False)

# Send temperature once every second.
while True:
    device.loop()
    if device.is_connected():
        # Call out to your sensor here
        temp = random.random() * 100
        device.send_state({"temperature": temp})
    time.sleep(1)

