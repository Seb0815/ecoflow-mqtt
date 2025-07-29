#!/usr/bin/env python3
"""
EcoFlow MQTT Data Validator
Überwacht MQTT-Topics und validiert die empfangenen Daten
"""

import json
import time
import sys
from datetime import datetime
import paho.mqtt.client as mqtt

# Validierungs-Metriken
validation_stats = {
    "total_messages": 0,
    "valid_messages": 0,
    "invalid_messages": 0,
    "enc_type_found": 0,
    "battery_soc_found": 0,
    "header_fields_found": 0,
    "device_data_found": 0,
    "start_time": datetime.now()
}

# Liste der Header-Felder die NICHT als Gerätedaten erscheinen sollen
# Diese stammen aus dem Protobuf-Header und sollten gefiltert werden
PROTOBUF_HEADER_FIELDS = {
    "src", "dest", "d_src", "d_dest", "enc_type", "check_type", 
    "cmd_func", "cmd_id", "data_len", "need_ack", "is_ack", 
    "seq", "product_id", "version", "payload_ver", "time_snap", 
    "is_rw_cmd", "is_queue", "ack_type", "code", "from", 
    "module_sn", "pdata"
}

# Erwartete Meta-Daten vom MQTT-Publisher (diese sind OK)
EXPECTED_MQTT_METADATA = {
    "device_sn", "device_type", "timestamp", "decoding_method", 
    "message_count", "raw_hex", "raw_bytes", "params"
}

def validate_message(topic, payload_str):
    """Validiert eine MQTT-Nachricht"""
    global validation_stats
    
    validation_stats["total_messages"] += 1
    
    try:
        payload = json.loads(payload_str)
        
        print(f"\n📨 Message #{validation_stats['total_messages']} - Topic: {topic}")
        print(f"📋 Parameters: {len(payload)} fields")
        
        # Prüfe auf Protobuf-Header-Felder (sollten gefiltert sein!)
        protobuf_header_found = False
        for field_name in payload.keys():
            if field_name in PROTOBUF_HEADER_FIELDS:
                print(f"🚨 PROBLEM: Protobuf header field found: {field_name} = {payload[field_name]}")
                validation_stats["header_fields_found"] += 1
                protobuf_header_found = True
                
                # Spezielle Behandlung für enc_type
                if field_name == "enc_type":
                    validation_stats["enc_type_found"] += 1
                    print(f"⚠️  enc_type value: {payload[field_name]} (should be filtered!)")
        
        # Prüfe auf erwartete MQTT-Meta-Daten (diese sind OK)
        mqtt_metadata_found = False
        for field_name in payload.keys():
            if field_name in EXPECTED_MQTT_METADATA:
                mqtt_metadata_found = True
        
        # Prüfe auf Device-Parameter in 'params'-Feld
        device_params = {}
        if "params" in payload and isinstance(payload["params"], dict):
            device_params = payload["params"]
            
            # Prüfe ob params Protobuf-Header enthalten (das wäre ein Problem!)
            for field_name in device_params.keys():
                if field_name in PROTOBUF_HEADER_FIELDS:
                    print(f"🚨 CRITICAL: Protobuf header in params: {field_name} = {device_params[field_name]}")
                    validation_stats["header_fields_found"] += 1
                    protobuf_header_found = True
        
        # Prüfe auf Battery SOC Daten
        battery_fields = ["battery_soc", "battery_soc_percent", "soc", "f32ShowSoc", "bmsBattSoc"]
        battery_found = False
        
        # Suche in device_params und Haupt-Payload
        all_fields = {**payload, **device_params}
        
        for field_name in battery_fields:
            if field_name in all_fields:
                print(f"🔋 Battery SOC: {field_name} = {all_fields[field_name]}")
                validation_stats["battery_soc_found"] += 1
                battery_found = True
        
        # Prüfe auf echte Gerätedaten
        device_fields = ["powGetPvSum", "powGetBpCms", "powGetSysGrid", "gridConnectionPower"]
        device_found = False
        for field_name in device_fields:
            if field_name in all_fields:
                print(f"⚡ Device data: {field_name} = {all_fields[field_name]}")
                validation_stats["device_data_found"] += 1
                device_found = True
        
        # Liste andere interessante Felder auf
        other_fields = []
        for field_name, value in all_fields.items():
            if (field_name not in PROTOBUF_HEADER_FIELDS and 
                field_name not in EXPECTED_MQTT_METADATA and
                field_name not in battery_fields and 
                field_name not in device_fields):
                other_fields.append(f"{field_name}={value}")
        
        if other_fields:
            print(f"📊 Other data: {', '.join(other_fields[:5])}" + ("..." if len(other_fields) > 5 else ""))
        
        # Validierung
        if protobuf_header_found:
            validation_stats["invalid_messages"] += 1
            print("❌ VALIDATION FAILED: Protobuf header fields present!")
        else:
            validation_stats["valid_messages"] += 1
            print("✅ VALIDATION PASSED: No protobuf header fields found")
            
    except json.JSONDecodeError as e:
        print(f"❌ JSON Parse Error: {e}")
        validation_stats["invalid_messages"] += 1
    except Exception as e:
        print(f"❌ Validation Error: {e}")
        validation_stats["invalid_messages"] += 1

def on_connect(client, userdata, flags, rc):
    print(f"🔗 Connected to MQTT broker with result code {rc}")
    client.subscribe("ecoflow/+/+")
    print("📡 Subscribed to ecoflow/+/+")

def on_message(client, userdata, msg):
    validate_message(msg.topic, msg.payload.decode())

def print_stats():
    """Druckt Validierungs-Statistiken"""
    runtime = datetime.now() - validation_stats["start_time"]
    
    print(f"\n" + "="*60)
    print(f"📊 VALIDATION STATISTICS (Runtime: {runtime})")
    print(f"="*60)
    print(f"Total messages:           {validation_stats['total_messages']}")
    print(f"Valid messages:           {validation_stats['valid_messages']}")
    print(f"Invalid messages:         {validation_stats['invalid_messages']}")
    print(f"enc_type found:           {validation_stats['enc_type_found']} ⚠️")
    print(f"Battery SOC found:        {validation_stats['battery_soc_found']} 🔋")
    print(f"Protobuf headers found:   {validation_stats['header_fields_found']} 🚨")
    print(f"Device data found:        {validation_stats['device_data_found']} ⚡")
    
    success_rate = (validation_stats['valid_messages'] / max(1, validation_stats['total_messages'])) * 100
    print(f"Success rate:        {success_rate:.1f}%")
    print(f"="*60)

def main():
    print("🔍 EcoFlow MQTT Data Validator starting...")
    print("🎯 Goal: Verify that header fields (like enc_type) are filtered out")
    print("📡 Monitoring all ecoflow topics...")
    
    # MQTT Client Setup
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    
    try:
        client.connect("192.168.252.20", 1883, 60)
        
        # Stats printer in separate thread
        import threading
        def stats_printer():
            while True:
                time.sleep(30)  # Print stats every 30 seconds
                print_stats()
        
        stats_thread = threading.Thread(target=stats_printer, daemon=True)
        stats_thread.start()
        
        client.loop_forever()
        
    except KeyboardInterrupt:
        print("\n🛑 Validation stopped by user")
        print_stats()
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        client.disconnect()

if __name__ == "__main__":
    main()
