from meshtastic import portnums_pb2, mesh_pb2, mqtt_pb2
import time
import re
from utils import generate_hash
from encryption import encrypt_packet

#################################
# Send Messages

def create_text_payload(node_id, destination_id, message_id, channel, key, message_text):
    encoded_message = mesh_pb2.Data()
    encoded_message.portnum = portnums_pb2.TEXT_MESSAGE_APP 
    encoded_message.payload = message_text.encode("utf-8")
    payload = generate_mesh_packet(node_id, destination_id, message_id, channel, key, encoded_message)
    return payload

def create_nodeinfo_payload(node_id, destination_id, node_long_name, node_short_name, node_hw_model, message_id, channel, key, want_response):
    user_payload = mesh_pb2.User()
    setattr(user_payload, "id", node_id)
    setattr(user_payload, "long_name", node_long_name)
    setattr(user_payload, "short_name", node_short_name)
    setattr(user_payload, "hw_model", node_hw_model)

    user_payload = user_payload.SerializeToString()

    encoded_message = mesh_pb2.Data()
    encoded_message.portnum = portnums_pb2.NODEINFO_APP
    encoded_message.payload = user_payload
    encoded_message.want_response = want_response  # Request NodeInfo back

    payload = generate_mesh_packet(node_id, destination_id, message_id, channel, key, encoded_message)
    return payload


def create_position_payload(node_id, destination_id, message_id, channel, key, lat, lon, alt):
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

    payload = generate_mesh_packet(node_id, destination_id, message_id, channel, key, encoded_message)
    return payload



def send_ack(node_id, destination_id, message_id, channel, key):

    encoded_message = mesh_pb2.Data()
    encoded_message.portnum = portnums_pb2.ROUTING_APP
    encoded_message.request_id = message_id
    encoded_message.payload = b"\030\000"

    payload = generate_mesh_packet(node_id, destination_id, message_id, channel, key, encoded_message)
    return payload


def generate_mesh_packet(node_id, destination_id, message_id, channel, key, encoded_message):

    node_number = int(node_id.replace("!", ""), 16)
    mesh_packet = mesh_pb2.MeshPacket()

    # Use the global message ID and increment it for the next call
    mesh_packet.id = message_id

    
    setattr(mesh_packet, "from", node_number)
    mesh_packet.to = destination_id
    mesh_packet.want_ack = False
    mesh_packet.channel = generate_hash(channel, key)
    mesh_packet.hop_limit = 3

    if key == "":
        mesh_packet.decoded.CopyFrom(encoded_message)
    else:
        mesh_packet.encrypted = encrypt_packet(channel, key, mesh_packet, encoded_message)

    service_envelope = mqtt_pb2.ServiceEnvelope()
    service_envelope.packet.CopyFrom(mesh_packet)
    service_envelope.channel_id = channel
    service_envelope.gateway_id = node_id

    payload = service_envelope.SerializeToString()

    return payload

