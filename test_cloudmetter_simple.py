#!/usr/bin/env python3
"""
Einfacher CloudMetter-Protobuf Test ohne Home Assistant
"""
import sys
import os

# Füge den Protobuf-Pfad hinzu
proto_path = '/Users/sebkutzke/Dev/ecoflow-mqtt/custom_components/ecoflow_cloud/devices/internal/proto'
sys.path.insert(0, proto_path)

print("=== CloudMetter Protobuf Test ===")

# Teste CloudMetter-Import
try:
    import stream_ac_pb2
    print("✅ stream_ac_pb2 erfolgreich importiert")
    
    # Teste CloudMetter-Klasse
    cloudmetter = stream_ac_pb2.CloudMetter()
    print(f"✅ CloudMetter-Objekt erstellt: {type(cloudmetter)}")
    
    # Zeige verfügbare Felder
    fields = [field.name for field in cloudmetter.DESCRIPTOR.fields]
    print(f"CloudMetter Felder: {fields}")
    
    # Teste Champ_cmd21_3
    cmd21_3 = stream_ac_pb2.Champ_cmd21_3()
    print(f"✅ Champ_cmd21_3-Objekt erstellt: {type(cmd21_3)}")
    
    # Prüfe ob cloudMetter-Field vorhanden ist
    cmd21_3_fields = [field.name for field in cmd21_3.DESCRIPTOR.fields]
    print(f"Champ_cmd21_3 Felder: {cmd21_3_fields}")
    
    if 'cloudMetter' in cmd21_3_fields:
        print("✅ cloudMetter-Field in Champ_cmd21_3 gefunden")
        
        # Teste CloudMetter-Objektzugriff
        print("Testing cloudMetter field access...")
        print(f"Has cloudMetter field: {cmd21_3.HasField('cloudMetter') if hasattr(cmd21_3, 'HasField') else 'N/A'}")
        
        # Versuche CloudMetter-Objekt zu setzen
        cmd21_3.cloudMetter.CopyFrom(cloudmetter)
        print("✅ CloudMetter-Objekt erfolgreich in Champ_cmd21_3 eingesetzt")
        
    else:
        print("❌ cloudMetter-Field in Champ_cmd21_3 NICHT gefunden")
        
except ImportError as e:
    print(f"❌ Import fehlgeschlagen: {e}")
except Exception as e:
    print(f"❌ Test fehlgeschlagen: {e}")

print("\n=== Prüfe MQTT-Publisher Parameter-Übertragung ===")

# Simuliere den Parameter-Filter aus stream_ac.py
test_params = {
    "soc": 85.5,
    "powGetPv1": 150.2,
    "cloudMetter.hasMeter": True,
    "cloudMetter.model": "CT_EF_04", 
    "cloudMetter.phaseAPower": -134.5,
    "cloudMetter.phaseBPower": 0.0,
    "cloudMetter.phaseCPower": 0.0,
    "cloudMetter.sn": "8b27e11a-test",
    "field_1234": 999,  # Debug-Field (sollte gefiltert werden)
    "Champ_cmd21_3_field999": 123  # Debug-Field (sollte gefiltert werden)
}

print(f"Test-Parameter vor Filterung: {len(test_params)}")
for key, value in test_params.items():
    print(f"  {key}: {value}")

# Simuliere die Filterlogik aus stream_ac.py
filtered_params = {}
field_params_count = 0

for key, value in test_params.items():
    # Nur reine field_xxx ohne Präfix entfernen (HeaderStream debug fields)
    # BEHALTE alle wichtigen Parameter mit Namen!
    should_filter = (
        # Filtere nur reine field_xxx (wie field_1066, field_1067)
        (key.startswith("field_") and key.count("_") == 1 and key[6:].isdigit()) or
        # Filtere Champ_cmd_fieldX nur wenn sie nicht in der Whitelist stehen
        (key.startswith("Champ_cmd") and "_field" in key and key not in [
            "Champ_cmd21_3_field460", "Champ_cmd21_3_field602", "Champ_cmd21_3_field254",
            "Champ_cmd21_3_field268", "Champ_cmd21_3_field282", "Champ_cmd21_3_field1002",
            "Champ_cmd21_3_field998"
        ])
    )
    
    if should_filter:
        field_params_count += 1
        continue
    
    # Behalte ALLE anderen Parameter für MQTT
    filtered_params[key] = value

print(f"\nParameter nach Filterung: {len(filtered_params)}")
print(f"Gefilterte Debug-Parameter: {field_params_count}")

for key, value in filtered_params.items():
    print(f"  {key}: {value}")

# Prüfe CloudMetter-Parameter
cloudmetter_params = {k: v for k, v in filtered_params.items() if 'cloudMetter' in k}
print(f"\nCloudMetter-Parameter für MQTT: {len(cloudmetter_params)}")
for key, value in cloudmetter_params.items():
    print(f"  ✅ {key}: {value}")

if cloudmetter_params:
    print("\n✅ CloudMetter-Parameter sollten an MQTT übertragen werden!")
else:
    print("\n❌ Keine CloudMetter-Parameter für MQTT gefunden!")

print("\n=== Test abgeschlossen ===")
