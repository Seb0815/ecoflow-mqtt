#!/usr/bin/env python3
"""
Einfacher Monitor zur Überwachung der empfangenen CMD-IDs
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

from custom_components.ecoflow_cloud.devices.internal.stream_ac import StreamAC
from custom_components.ecoflow_cloud.devices.internal.proto import stream_ac_pb2 as stream_ac
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
_LOGGER = logging.getLogger(__name__)

class CMDMonitor:
    def __init__(self):
        self.cmd_counts = {}
        self.soc_found = False
        
    def analyze_payload(self, raw_data: bytes):
        """Analysiert Payload und überwacht CMD-IDs"""
        try:
            packet = stream_ac.SendHeaderStreamMsg()
            packet.ParseFromString(raw_data)
            
            cmd_id = packet.msg.cmd_id
            
            # Zähle CMD-IDs
            self.cmd_counts[cmd_id] = self.cmd_counts.get(cmd_id, 0) + 1
            
            _LOGGER.info(f"📊 CMD {cmd_id} empfangen (#{self.cmd_counts[cmd_id]})")
            
            # Spezielle Behandlung für CMD 50
            if cmd_id == 50:
                _LOGGER.warning(f"🎯 CMD 50 GEFUNDEN! Versuche SOC-Extraktion...")
                self.try_extract_soc(packet)
            
            # Status alle 10 Nachrichten
            total = sum(self.cmd_counts.values())
            if total % 10 == 0:
                _LOGGER.info(f"📈 CMD-Verteilung nach {total} Nachrichten: {dict(sorted(self.cmd_counts.items()))}")
                
        except Exception as e:
            _LOGGER.error(f"Fehler bei Payload-Analyse: {e}")
    
    def try_extract_soc(self, packet):
        """Versucht SOC aus CMD 50 zu extrahieren"""
        try:
            if hasattr(packet.msg, "pdata"):
                from custom_components.ecoflow_cloud.devices.internal.proto import stream_ac_pb2 as stream_ac2
                
                # Versuche CMD 50 Parsing
                content = stream_ac2.Champ_cmd50_3()
                content.ParseFromString(packet.msg.pdata)
                
                # Prüfe auf SOC-Feld
                if hasattr(content, 'soc') and content.HasField('soc'):
                    soc_value = getattr(content, 'soc')
                    _LOGGER.error(f"🔥 ECHTER SOC GEFUNDEN: {soc_value}%")
                    self.soc_found = True
                else:
                    _LOGGER.warning("❌ CMD 50 empfangen, aber SOC-Feld nicht gefunden")
                    
                    # Liste alle verfügbaren Felder
                    fields = []
                    for descriptor in content.DESCRIPTOR.fields:
                        if content.HasField(descriptor.name):
                            value = getattr(content, descriptor.name)
                            fields.append(f"{descriptor.name}={value}")
                    
                    if fields:
                        _LOGGER.info(f"📋 CMD 50 Felder: {', '.join(fields[:5])}{'...' if len(fields) > 5 else ''}")
                    else:
                        _LOGGER.warning("❌ Keine Felder in CMD 50 dekodiert")
                        
        except Exception as e:
            _LOGGER.warning(f"CMD 50 Parsing-Fehler: {e}")

# Fake MQTT-Client für Testing
class FakeMQTTClient:
    def __init__(self):
        self.monitor = CMDMonitor()
        
    def process_message(self, payload_hex: str):
        """Verarbeitet eine Hex-Nachricht"""
        try:
            payload = bytes.fromhex(payload_hex.replace(" ", ""))
            self.monitor.analyze_payload(payload)
        except Exception as e:
            _LOGGER.error(f"Fehler bei Hex-Verarbeitung: {e}")

if __name__ == "__main__":
    print("🔍 CMD Monitor gestartet")
    print("Fügen Sie Hex-Payloads ein (eine pro Zeile, CTRL+C zum Beenden):")
    
    client = FakeMQTTClient()
    
    try:
        while True:
            try:
                line = input().strip()
                if line:
                    client.process_message(line)
            except EOFError:
                break
    except KeyboardInterrupt:
        print(f"\n📊 Finale CMD-Statistik: {client.monitor.cmd_counts}")
        print(f"🎯 SOC gefunden: {'Ja' if client.monitor.soc_found else 'Nein'}")
