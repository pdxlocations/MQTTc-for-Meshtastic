from meshtastic import mqtt_pb2, portnums_pb2, mesh_pb2, telemetry_pb2
from meshtastic import protocols
from encryption import decrypt_packet
from load_config import key

def on_message(client, userdata, msg):
    se = mqtt_pb2.ServiceEnvelope()
    try:
        se.ParseFromString(msg.payload)

        print ("")
        print ("Service Envelope:")
        print (se)

        mp = se.packet
    except Exception as e:
        print(f"*** ServiceEnvelope: {str(e)}")
        return
    
    if mp.HasField("encrypted") and not mp.HasField("decoded"):
        decoded_data = decrypt_packet(mp, key)
        mp.decoded.CopyFrom(decoded_data)

    print ("")
    print ("Message Packet:")
    print(mp)

    if mp.decoded.portnum == portnums_pb2.TEXT_MESSAGE_APP:
        try:
            from_str = getattr(mp, "from")
            from_id = '!' + hex(from_str)[2:]
            text_payload = mp.decoded.payload.decode("utf-8")

            print ("")
            print ("Message Payload:")
            print (mp.decoded)
            # print(f"{from_id}: {text_payload}")

        except Exception as e:
            print(f"*** TEXT_MESSAGE_APP: {str(e)}")
        
    elif mp.decoded.portnum == portnums_pb2.NODEINFO_APP:
        info = mesh_pb2.User()
        try:
            info.ParseFromString(mp.decoded.payload)

            print("")
            print("NodeInfo:")
            print(info)

        except Exception as e:
            print(f"*** NODEINFO_APP: {str(e)}")
        
    elif mp.decoded.portnum == portnums_pb2.POSITION_APP:
        pos = mesh_pb2.Position()
        try:
            pos.ParseFromString(mp.decoded.payload)

            print("")
            print("Position:")
            print(pos)

        except Exception as e:
            print(f"*** POSITION_APP: {str(e)}")

    elif mp.decoded.portnum == portnums_pb2.TELEMETRY_APP:
        telem = telemetry_pb2.Telemetry()
        try:
            # Parse the payload into the main telemetry message
            telem.ParseFromString(mp.decoded.payload)

            # Check and parse device_metrics if available
            if telem.HasField("device_metrics"):
                device_metrics = telem.device_metrics
                print("Device Metrics:")
                print(device_metrics)

            # Check and parse environment_metrics if available
            if telem.HasField("environment_metrics"):
                environment_metrics = telem.environment_metrics
                print("Environment Metrics:")
                print(environment_metrics)

            # Check and parse power_metrics if available
            if telem.HasField("power_metrics"):
                power_metrics = telem.power_metrics
                print("Power Metrics:")
                print(power_metrics)

        except Exception as e:
            print(f"*** TELEMETRY_APP: {str(e)}")


    elif handler.protobufFactory is not None:
            portNumInt = mp.decoded.portnum
            handler = protocols.get(portNumInt)
            pb = handler.protobufFactory()
            pb.ParseFromString(mp.decoded.payload)
            print("")
            print("Mesh Packet:")
            print(pb)

        # rssi = getattr(mp, "rx_rssi")

        # # Device Metrics
        # device_metrics_dict = {
        #     'Battery Level': telem.device_metrics.battery_level,
        #     'Voltage': round(telem.device_metrics.voltage, 2),
        #     'Channel Utilization': round(telem.device_metrics.channel_utilization, 1),
        #     'Air Utilization': round(telem.device_metrics.air_util_tx, 1)
        # }

        # # Environment Metrics
        # environment_metrics_dict = {
        #     'Temp': round(telem.environment_metrics.temperature, 2),
        #     'Humidity': round(telem.environment_metrics.relative_humidity, 0),
        #     'Pressure': round(telem.environment_metrics.barometric_pressure, 2),
        #     'Gas Resistance': round(telem.environment_metrics.gas_resistance, 2)
        # }
