FROM python:3.11

WORKDIR /app

# Kopiere Skript und Requirements
COPY ecoflow_mqtt.py .
COPY requirements.txt .

# Installiere Python-Abhängigkeiten
RUN pip install --upgrade pip && \
    pip install -r requirements.txt && \
    git clone https://github.com/tolwi/hassio-ecoflow-cloud.git /tmp/ecoflow-cloud && \
    cp -r /tmp/ecoflow-cloud/custom_components/ecoflow_cloud /app/ecoflow_cloud

# Startkommando
CMD ["python3", "ecoflow_mqtt.py"]
