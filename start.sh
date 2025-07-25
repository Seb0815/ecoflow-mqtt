#!/bin/bash

# EcoFlow Cloud MQTT Publisher Start Script
# Lädt .env Datei und startet den Publisher

set -e

echo "🚀 EcoFlow Cloud MQTT Publisher wird gestartet..."

# Arbeitsverzeichnis wechseln
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# .env Datei laden, falls vorhanden
if [ -f .env ]; then
    echo "📝 Lade Konfiguration aus .env..."
    export $(grep -v '^#' .env | xargs)
else
    echo "⚠️  Keine .env Datei gefunden. Kopiere .env.example zu .env und fülle deine Daten aus."
    if [ -f .env.example ]; then
        echo "💡 Beispiel-Konfiguration ist verfügbar in .env.example"
    fi
    exit 1
fi

# Python Dependencies prüfen
echo "🔍 Prüfe Python Dependencies..."
python3 -c "
import sys
try:
    import paho.mqtt.client
    import aiohttp
    print('✅ Alle Dependencies gefunden')
except ImportError as e:
    print(f'❌ Fehlende Dependency: {e}')
    print('💡 Installiere mit: pip install -r requirements_standalone.txt')
    sys.exit(1)
"

if [ $? -ne 0 ]; then
    exit 1
fi

# Konfiguration testen (optional)
if [ "${1}" == "--test" ]; then
    echo "🧪 Teste Konfiguration..."
    python3 test_config.py
    exit $?
fi

# Publisher starten
echo "🎯 Starte EcoFlow Cloud MQTT Publisher..."
exec python3 ecoflow_cloud_mqtt.py
