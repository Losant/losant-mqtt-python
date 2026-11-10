import random
import time

from losantmqtt import AuthError, Device

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
try:
    while True:
        # loop() drives the network. Bad credentials raise AuthError from here.
        device.loop()
        if device.is_connected():
            # Call out to your sensor here
            temp = random.random() * 100
            device.send_state({"temperature": temp})
        time.sleep(1)
except AuthError as err:
    raise SystemExit(f"Could not authenticate: {err}") from err
except KeyboardInterrupt:
    device.close()
