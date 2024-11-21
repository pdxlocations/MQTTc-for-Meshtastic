#!/usr/bin/env python3
"""
Powered by Meshtastic™ https://meshtastic.org/
"""

from meshtastic.protobuf import mesh_pb2, mqtt_pb2, portnums_pb2, telemetry_pb2
from meshtastic import BROADCAST_NUM
import paho.mqtt.client as mqtt
import random
import time
import ssl
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
import base64
import argparse
import re


from load_config import (
    mqtt_broker, mqtt_port, mqtt_username, mqtt_password,
    root_topic, channel, key, node_name, node_short_name,
    node_long_name, lat, lon, alt, node_hw_model, node_number
)

#### Debug Options
debug = True
auto_reconnect = True
auto_reconnect_delay = 1 # seconds
print_service_envelope = False
print_message_packet = False

stay_connected = False
print_node_info =  False
print_node_position = False
print_node_telemetry = False

#### Parser Arguments
parser = argparse.ArgumentParser(add_help=True)
parser.add_argument('--config', type=str, default='config.py', help='Path to the config file')
parser.add_argument('--message', type=str, help='The message to send')
parser.add_argument('--lat', type=float, help='Latitude coordinate')
parser.add_argument('--lon', type=float, help='Longitude coordinate')
parser.add_argument('--alt', type=float, help='Altitude')
args = parser.parse_args()




#################################
### Program variables

default_key = "1PG7OiApB1nwvP+rz05pAQ==" # AKA AQ==
global_message_id = random.getrandbits(32)

#################################
# Program Base Functions
    
def set_topic():
    if debug: print(f"set_topic: {root_topic}{channel}/")
    global subscribe_topic, publish_topic, node_number, node_name
    node_name = '!' + hex(node_number)[2:]
    subscribe_topic = root_topic + channel + "/#"
    publish_topic = root_topic + channel + "/" + node_name

def xor_hash(data):
    result = 0
    for char in data:
        result ^= char
    return result

def generate_hash(name, key):
    replaced_key = key.replace('-', '+').replace('_', '/')
    key_bytes = base64.b64decode(replaced_key.encode('utf-8'))
    h_name = xor_hash(bytes(name, 'utf-8'))
    h_key = xor_hash(key_bytes)
    result = h_name ^ h_key
    return result

def validate_lat_lon_alt(args):
    # Check if --alt is provided
    if args.alt:
        if not args.lat or not args.lon:
            parser.error('--alt should not be provided without --lat and --lon.')

    # Check if lat and lon are provided
    if args.lat or args.lon:
        # If one of lat or lon is provided, ensure both are provided
        if not (args.lat and args.lon):
            parser.error('If you specify --lat or --lon, you must specify both --lat and --lon.')


#################################
# Receive Messages

def on_message(client, userdata, msg):
    se = mqtt_pb2.ServiceEnvelope()
    try:
        se.ParseFromString(msg.payload)
        if print_service_envelope:
            print ("")
            print ("Service Envelope:")
            print (se)
        mp = se.packet
    except Exception as e:
        print(f"*** ServiceEnvelope: {str(e)}")
        return
    
    if mp.HasField("encrypted") and not mp.HasField("decoded"):
        decode_encrypted(mp)

    if print_message_packet: 
        print ("")
        print ("Message Packet:")
        print(mp)

    if mp.decoded.portnum == portnums_pb2.TEXT_MESSAGE_APP:
        try:
            from_str = getattr(mp, "from")
            from_id = '!' + hex(from_str)[2:]
            text_payload = mp.decoded.payload.decode("utf-8")
            print(f"{from_id}: {text_payload}")
        except Exception as e:
            print(f"*** TEXT_MESSAGE_APP: {str(e)}")
        
    elif mp.decoded.portnum == portnums_pb2.NODEINFO_APP:
        info = mesh_pb2.User()
        try:
            info.ParseFromString(mp.decoded.payload)
            if print_node_info:
                print("")
                print("NodeInfo:")
                print(info)
        except Exception as e:
            print(f"*** NODEINFO_APP: {str(e)}")
        
    elif mp.decoded.portnum == portnums_pb2.POSITION_APP:
        pos = mesh_pb2.Position()
        try:
            pos.ParseFromString(mp.decoded.payload)
            if print_node_position:
                print("")
                print("Position:")
                print(pos)
        except Exception as e:
            print(f"*** POSITION_APP: {str(e)}")

    elif mp.decoded.portnum == portnums_pb2.TELEMETRY_APP:
        env = telemetry_pb2.Telemetry()
        try:
            env.ParseFromString(mp.decoded.payload)
            if print_node_telemetry:
                print("")
                print("Telemetry:")
                print(env)
        except Exception as e:
            print(f"*** TELEMETRY_APP: {str(e)}")

        rssi = getattr(mp, "rx_rssi")

        # Device Metrics
        device_metrics_dict = {
            'Battery Level': env.device_metrics.battery_level,
            'Voltage': round(env.device_metrics.voltage, 2),
            'Channel Utilization': round(env.device_metrics.channel_utilization, 1),
            'Air Utilization': round(env.device_metrics.air_util_tx, 1)
        }

        # Environment Metrics
        environment_metrics_dict = {
            'Temp': round(env.environment_metrics.temperature, 2),
            'Humidity': round(env.environment_metrics.relative_humidity, 0),
            'Pressure': round(env.environment_metrics.barometric_pressure, 2),
            'Gas Resistance': round(env.environment_metrics.gas_resistance, 2)
        }


def decode_encrypted(mp):
        try:
            # Convert key to bytes
            key_bytes = base64.b64decode(key.encode('ascii'))
      
            nonce_packet_id = getattr(mp, "id").to_bytes(8, "little")
            nonce_from_node = getattr(mp, "from").to_bytes(8, "little")

            # Put both parts into a single byte array.
            nonce = nonce_packet_id + nonce_from_node

            cipher = Cipher(algorithms.AES(key_bytes), modes.CTR(nonce), backend=default_backend())
            decryptor = cipher.decryptor()
            decrypted_bytes = decryptor.update(getattr(mp, "encrypted")) + decryptor.finalize()

            data = mesh_pb2.Data()
            data.ParseFromString(decrypted_bytes)
            mp.decoded.CopyFrom(data)

        except Exception as e:

            if print_message_packet: print(f"failed to decrypt: \n{mp}")
            if debug: print(f"*** Decryption failed: {str(e)}")
            return


#################################
# Send Messages

def publish_message(destination_id, message_text):

    if debug: print("publish_message")

    if not client.is_connected():
        connect_mqtt()

    if message_text:
        encoded_message = mesh_pb2.Data()
        encoded_message.portnum = portnums_pb2.TEXT_MESSAGE_APP 
        encoded_message.payload = message_text.encode("utf-8")
        generate_mesh_packet(destination_id, encoded_message)
    else:
        return

def send_node_info(destination_id, want_response):
    if debug: print("send_node_info")

    if not client.is_connected():
        connect_mqtt()

    user_payload = mesh_pb2.User()
    setattr(user_payload, "id", node_name)
    setattr(user_payload, "long_name", node_long_name)
    setattr(user_payload, "short_name", node_short_name)
    setattr(user_payload, "hw_model", node_hw_model)

    user_payload = user_payload.SerializeToString()

    encoded_message = mesh_pb2.Data()
    encoded_message.portnum = portnums_pb2.NODEINFO_APP
    encoded_message.payload = user_payload
    encoded_message.want_response = want_response  # Request NodeInfo back

    # print(encoded_message)
    generate_mesh_packet(destination_id, encoded_message)


def send_position(destination_id, lat, lon, alt):

    if debug: print("send_Position")

    if not client.is_connected():
        connect_mqtt()

    if debug: print(f"Sending Position Packet to {str(destination_id)}")

    pos_time = int(time.time())
    latitude_str = str(lat)
    longitude_str = str(lon)

    try:
        latitude = float(latitude_str)  # Convert latitude to a float
    except ValueError:
        latitude = 0.0
    try:
        longitude = float(longitude_str)  # Convert longitude to a float
    except ValueError:
        longitude = 0.0

    latitude = latitude * 1e7
    longitude = longitude * 1e7

    latitude_i = int(latitude)
    longitude_i = int(longitude)

    altitude_str = str(alt)
    altitude_units = 1 / 3.28084 if 'ft' in altitude_str else 1.0
    altitude_number_of_units = float(re.sub('[^0-9.]','', altitude_str))
    altitude_i = int(altitude_units * altitude_number_of_units) # meters

    position_payload = mesh_pb2.Position()
    setattr(position_payload, "latitude_i", latitude_i)
    setattr(position_payload, "longitude_i", longitude_i)
    setattr(position_payload, "altitude", altitude_i)
    setattr(position_payload, "time", pos_time)

    position_payload = position_payload.SerializeToString()

    encoded_message = mesh_pb2.Data()
    encoded_message.portnum = portnums_pb2.POSITION_APP
    encoded_message.payload = position_payload
    encoded_message.want_response = True

    generate_mesh_packet(destination_id, encoded_message)


def generate_mesh_packet(destination_id, encoded_message):
    global global_message_id
    mesh_packet = mesh_pb2.MeshPacket()

    # Use the global message ID and increment it for the next call
    mesh_packet.id = global_message_id
    if global_message_id == 4294967295:
        global_message_id = 0
    global_message_id += 1
    
    setattr(mesh_packet, "from", node_number)
    mesh_packet.to = destination_id
    mesh_packet.want_ack = False
    mesh_packet.channel = generate_hash(channel, key)
    mesh_packet.hop_limit = 3

    if key == "":
        mesh_packet.decoded.CopyFrom(encoded_message)
    else:
        mesh_packet.encrypted = encrypt_message(channel, key, mesh_packet, encoded_message)

    service_envelope = mqtt_pb2.ServiceEnvelope()
    service_envelope.packet.CopyFrom(mesh_packet)
    service_envelope.channel_id = channel
    service_envelope.gateway_id = node_name
    # print (service_envelope)

    payload = service_envelope.SerializeToString()
    # set_topic()
    # print(payload)
    client.publish(root_topic + channel + "/" + node_name, payload)

def encrypt_message(channel, key, mesh_packet, encoded_message):

    mesh_packet.channel = generate_hash(channel, key)
    key_bytes = base64.b64decode(key.encode('ascii'))

    nonce_packet_id = mesh_packet.id.to_bytes(8, "little")
    nonce_from_node = node_number.to_bytes(8, "little")

    # Put both parts into a single byte array.
    nonce = nonce_packet_id + nonce_from_node

    cipher = Cipher(algorithms.AES(key_bytes), modes.CTR(nonce), backend=default_backend())
    encryptor = cipher.encryptor()
    encrypted_bytes = encryptor.update(encoded_message.SerializeToString()) + encryptor.finalize()

    return encrypted_bytes

def send_ack(destination_id, message_id):
    if debug: print("Sending ACK")

    encoded_message = mesh_pb2.Data()
    encoded_message.portnum = portnums_pb2.ROUTING_APP
    encoded_message.request_id = message_id
    encoded_message.payload = b"\030\000"

    generate_mesh_packet(destination_id, encoded_message)


#################################
# MQTT Server 
    
def connect_mqtt():

    if "tls_configured" not in connect_mqtt.__dict__:
        connect_mqtt.tls_configured = False

    global mqtt_broker, mqtt_port, mqtt_username, mqtt_password, root_topic, channel, node_number, key
    if not client.is_connected():
        if debug: print("connect_mqtt")
        try:
            if ':' in mqtt_broker:
                mqtt_broker,mqtt_port = mqtt_broker.split(':')
                mqtt_port = int(mqtt_port)

            if key == "AQ==":
                key = default_key

            padded_key = key.ljust(len(key) + ((4 - (len(key) % 4)) % 4), '=')
            replaced_key = padded_key.replace('-', '+').replace('_', '/')
            key = replaced_key

            client.username_pw_set(mqtt_username, mqtt_password)
            if mqtt_port == 8883 and connect_mqtt.tls_configured == False:
                client.tls_set(ca_certs="cacert.pem", tls_version=ssl.PROTOCOL_TLSv1_2)
                client.tls_insecure_set(False)
                connect_mqtt.tls_configured = True
            client.connect(mqtt_broker, mqtt_port, 60)
        except Exception as e:
            print (e)
        

def on_disconnect(client, userdata, flags, reason_code, properties):
    if debug: print("client is disconnected")
    if reason_code != 0:
        if auto_reconnect == True:
            print("attempting to reconnect in " + str(auto_reconnect_delay) + " second(s)")
            time.sleep(auto_reconnect_delay)
            connect_mqtt()

def on_connect(client, userdata, flags, reason_code, properties):
    set_topic()
    if client.is_connected():
        print("client is connected")
    
    if reason_code == 0:
        if debug: print(f"Publish Topic is: {publish_topic}")
        if debug: print(f"Subscribe Topic is: {subscribe_topic}")
        client.subscribe(subscribe_topic)
    else:
        print("Failed to connect, return code %d\n", reason_code)

############################
# Main 


client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="", clean_session=True, userdata=None)
client.on_connect = on_connect
client.on_disconnect = on_disconnect
client.on_message = on_message

connect_mqtt()
client.loop_start()
time.sleep(1)

send_node_info(BROADCAST_NUM, want_response=False)
time.sleep(3)

if args.message:
    publish_message(BROADCAST_NUM, args.message)
    time.sleep(3)

if args.lat:
    validate_lat_lon_alt(args)
    lat = args.lat
    lon = args.lon
    if args.alt:
        alt = args.alt
    send_position(BROADCAST_NUM, lat, lon, alt=0)
    time.sleep(3)

if not stay_connected:
    client.disconnect()
else:
    while True:
        time.sleep(1)
    