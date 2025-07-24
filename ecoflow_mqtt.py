import os
import time
import paho.mqtt.client as mqtt
from ecoflow_cloud import EcoflowCloud

# Umgebungsvariablen
EMAIL = os.getenv("EF_EMAIL")
PASSWORD = os.getenv("EF_PASSWORD")
DEVICE_ID = os.getenv("EF_DEVICE_ID")
MQTT_HOST = os.getenv("MQTT_HOST")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))

# MQTT verbinden
mqttc = mqtt.Client()
mqttc.connect(MQTT_HOST, MQTT_PORT)

# API Login & Abfrage
api = EcoflowCloud()
api.login(EMAIL, PASSWORD)

while True:
    data = api.get_device_details(DEVICE_ID)
    for key, value in data.items():
        topic = f"ecoflow/stream_ultra/{key}"
        mqttc.publish(topic, str(value))
    time.sleep(60)  # Abfrageintervall: 1 Minute
