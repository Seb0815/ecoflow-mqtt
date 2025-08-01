#!/usr/bin/env python3
"""
Test-Script für CloudMetter-Debugging
Überprüft ob CloudMetter-Daten verarbeitet und erkannt werden
"""
import sys
import os
import logging

# Füge den ecoflow_cloud Pfad hinzu
sys.path.append('/Users/sebkutzke/Dev/ecoflow-mqtt/custom_components')

# Logging konfigurieren
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from ecoflow_cloud.devices.internal.stream_ac import StreamAC
from ecoflow_cloud.sensor import extract_sensor_parameters_from_device_class

# Teste Parameter-Extraktion
print("=== CloudMetter Parameter Test ===")

# Extrahiere alle definierten Parameter
defined_params = StreamAC.get_defined_parameters()
print(f"Anzahl definierter Parameter: {len(defined_params)}")

# Suche nach CloudMetter-Parametern
cloudmetter_params = [p for p in defined_params if 'cloudMetter' in p]
print(f"CloudMetter-Parameter gefunden: {len(cloudmetter_params)}")

for param in cloudmetter_params:
    print(f"  - {param}")

# Teste CloudMetter-Protobuf-Import
print("\n=== CloudMetter Protobuf Test ===")
try:
    from ecoflow_cloud.devices.internal.proto.stream_ac_pb2 import CloudMetter
    print("✅ CloudMetter protobuf erfolgreich importiert")
    
    # Erstelle leeres CloudMetter-Objekt zum Testen
    test_cloudmetter = CloudMetter()
    print(f"✅ CloudMetter-Objekt erstellt: {type(test_cloudmetter)}")
    print(f"Available fields: {[field.name for field in test_cloudmetter.DESCRIPTOR.fields]}")
    
except ImportError as e:
    print(f"❌ CloudMetter protobuf Import fehlgeschlagen: {e}")

# Teste Champ_cmd21_3 Import
print("\n=== Champ_cmd21_3 Test ===")
try:
    from ecoflow_cloud.devices.internal.proto.stream_ac_pb2 import Champ_cmd21_3
    print("✅ Champ_cmd21_3 protobuf erfolgreich importiert")
    
    # Prüfe ob cloudMetter-Field vorhanden ist
    test_cmd21_3 = Champ_cmd21_3()
    fields = [field.name for field in test_cmd21_3.DESCRIPTOR.fields]
    print(f"Available fields: {fields}")
    
    if 'cloudMetter' in fields:
        print("✅ cloudMetter-Field in Champ_cmd21_3 gefunden")
    else:
        print("❌ cloudMetter-Field in Champ_cmd21_3 NICHT gefunden")
        
except ImportError as e:
    print(f"❌ Champ_cmd21_3 protobuf Import fehlgeschlagen: {e}")

print("\n=== Test abgeschlossen ===")
