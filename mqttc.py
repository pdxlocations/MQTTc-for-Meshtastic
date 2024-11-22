#!/usr/bin/env python3
"""
Powered by Meshtastic™ https://meshtastic.org/
"""

import time
import paho.mqtt.client as mqtt

from tx_message_handler import send_nodeinfo, send_position, send_device_telemetry, send_text_message
from rx_message_handler import on_message
from load_config import mqtt_broker, mqtt_port, mqtt_username, mqtt_password
from mqtt_handler import connect_mqtt, on_connect, on_disconnect
from argument_parser import handle_args

stay_connected = True

def main():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="", clean_session=True, userdata=None)
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message

    connect_mqtt(client, mqtt_broker, mqtt_port, mqtt_username, mqtt_password)
    client.loop_start()
    time.sleep(1)

    send_nodeinfo(client)
    time.sleep(1)

    # send_position(client, lat=45.0, lon=-120.0, alt=0.0)
    # time.sleep(1)

    send_device_telemetry(client, battery_level=69, voltage=4.0, chutil=3, airtxutil=1, uptime=420)
    time.sleep(1)

    # send_text_message(client, "Happy New Year!")
    # time.sleep(1)

    handle_args(client)

    if not stay_connected:
        client.disconnect()
    else:
        while True:
            time.sleep(1)

if __name__ == "__main__":
    main()