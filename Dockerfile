# 🌱 Basis-Image mit Python 3.11
FROM python:3.11

# 📁 Arbeitsverzeichnis setzen
WORKDIR /app

# 📦 requirements.txt und ecoflow_mqtt.py ins Image kopieren
COPY requirements.txt .
COPY ecoflow_mqtt.py .

# 🧠 MQTT + Requests installieren + Git-Repo klonen + Modul kopieren
RUN pip install --upgrade pip && \
    pip install -r requirements.txt && \
    git clone https://github.com/tolwi/hassio-ecoflow-cloud.git /tmp/ecoflow-cloud && \
    cp /tmp/ecoflow-cloud/custom_components/ecoflow_cloud/api.py /app/ecoflow_cloud.py

# 🏁 Startkommando
CMD ["python3", "ecoflow_mqtt.py"]
