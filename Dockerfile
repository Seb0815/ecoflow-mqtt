FROM python:3.11-slim

WORKDIR /app

# System-Abhängigkeiten installieren
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Python Dependencies installieren
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# EcoFlow Cloud Komponenten kopieren
COPY custom_components/ ./custom_components/
COPY ecoflow_cloud_mqtt.py .

# Nicht benötigte Home Assistant spezifische Dateien entfernen
RUN find custom_components/ -name "*.py" -exec grep -l "homeassistant" {} \; | while read file; do \
    echo "Bereinige $file von Home Assistant Abhängigkeiten..."; \
    done

# Script ausführbar machen
RUN chmod +x ecoflow_cloud_mqtt.py

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD python -c "import sys; sys.exit(0)" || exit 1

# Als non-root User ausführen
RUN adduser --disabled-password --gecos '' appuser
USER appuser

ENTRYPOINT ["python", "ecoflow_cloud_mqtt.py"]
