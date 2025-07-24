import os
import time
import logging
import paho.mqtt.client as mqtt
from ecoflow_cloud import EcoflowCloud, EcoflowException

# 🔐 Konfiguration aus Umgebung
EMAIL = os.getenv("EF_EMAIL")
PASSWORD = os.getenv("EF_PASSWORD")
DEVICE_ID = os.getenv("EF_DEVICE_ID")
MQTT_HOST = os.getenv("MQTT_HOST", "mqtt.local")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
INTERVAL = int(os.getenv("EF_INTERVAL", "60"))  # Abfrageintervall (sek)

# 📝 Logging Setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

logging.info("EcoFlow MQTT Publisher startet...")

# 📡 MQTT Verbindung
try:
    mqttc = mqtt.Client()
    mqttc.connect(MQTT_HOST, MQTT_PORT)
    logging.info(f"Verbunden mit MQTT Broker: {MQTT_HOST}:{MQTT_PORT}")
except Exception as e:
    logging.error(f"Fehler beim Verbinden mit MQTT: {e}")
    exit(1)

# 🔑 Login zur Cloud API
try:
    api = EcoflowCloud()
    api.login(EMAIL, PASSWORD)
    logging.info("Login bei EcoFlow API erfolgreich")
except EcoflowException as e:
    logging.error(f"Login fehlgeschlagen: {e}")
    exit(1)

# 🔁 Abfrage-Schleife
while True:
    try:
        data = api.get_device_details(DEVICE_ID)
        for key, value in data.items():
            topic = f"ecoflow/stream_ultra/{key}"
            mqttc.publish(topic, str(value))
        logging.info(f"{len(data)} Werte veröffentlicht für Device {DEVICE_ID}")
    except EcoflowException as e:
        logging.warning(f"Fehler beim Abrufen der Gerätedaten: {e}")
    except Exception as e:
        logging.error(f"Allgemeiner Fehler: {e}")

    time.sleep(INTERVAL)
