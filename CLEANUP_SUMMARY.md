# EcoFlow MQTT - Home Assistant Bereinigung

## 🎯 Ziel
Die EcoFlow Cloud Integration von Home Assistant Abhängigkeiten befreien und als eigenständigen MQTT Publisher verfügbar machen.

## ✅ Durchgeführte Änderungen

### 1. **Neue Standalone Dateien**

- **`ecoflow_cloud_mqtt.py`** - Hauptanwendung für standalone MQTT Publishing
- **`standalone_mqtt_client.py`** - MQTT Client ohne Home Assistant Abhängigkeiten  
- **`requirements_standalone.txt`** - Python Dependencies für standalone Version
- **`.env.example`** - Beispiel-Konfiguration
- **`README_STANDALONE.md`** - Dokumentation für standalone Version
- **`docker-compose.standalone.yml`** - Docker Compose für standalone Deployment
- **`Dockerfile.standalone`** - Docker Image für standalone Version
- **`start.sh`** - Start-Script mit .env Support
- **`test_config.py`** - Konfigurationstester

### 2. **Bereinigte Dateien**

- **`custom_components/ecoflow_cloud/__init__.py`** - Home Assistant spezifische Funktionen entfernt

### 3. **Konfiguration**

#### Umgebungsvariablen für Standalone Version:
```bash
# EcoFlow API
ECOFLOW_AUTH_TYPE=private|public
ECOFLOW_USERNAME=email@example.com
ECOFLOW_PASSWORD=password
ECOFLOW_ACCESS_KEY=key (für public API)
ECOFLOW_SECRET_KEY=secret (für public API)
ECOFLOW_DEVICES=SN:TYPE:NAME,SN:TYPE:NAME

# MQTT
MQTT_HOST=localhost
MQTT_PORT=1883
MQTT_BASE_TOPIC=ecoflow
REFRESH_INTERVAL=30
```

## 🚀 Verwendung

### Option 1: Docker Compose (Empfohlen)
```bash
cp .env.example .env
# .env bearbeiten
docker-compose -f docker-compose.standalone.yml up -d
```

### Option 2: Lokale Installation
```bash
pip install -r requirements_standalone.txt
# Umgebungsvariablen setzen
python ecoflow_cloud_mqtt.py
```

### Option 3: Mit Start-Script
```bash
cp .env.example .env
# .env bearbeiten  
./start.sh
```

## 📊 MQTT Output

Daten werden in folgender Struktur veröffentlicht:
```
ecoflow/
├── {device_sn}/
│   ├── battery_level
│   ├── ac_out_power
│   ├── solar_in_power
│   └── status (JSON mit Metadaten)
```

## 🧪 Testing

```bash
# Konfiguration testen
python test_config.py

# Mit Start-Script
./start.sh --test
```

## 🔧 Features

✅ **Standalone** - Keine Home Assistant erforderlich  
✅ **Multi-Device** - Mehrere EcoFlow Geräte gleichzeitig  
✅ **Dual API** - Private (Email/Password) & Public API (Keys)  
✅ **Docker Ready** - Vollständige Container-Unterstützung  
✅ **MQTT Forwarding** - Alle EcoFlow Daten per MQTT  
✅ **Auto-Discovery** - Automatische Geräteerkennung  
✅ **Flexible Config** - Umgebungsvariablen & .env Support  

## 🎁 Bonus Features

- **Integrierter MQTT Broker** (Mosquitto) in Docker Compose
- **MQTT Explorer** Web-UI für Debugging
- **Graceful Shutdown** mit Signal-Handling
- **Health Checks** für Container
- **Detaillierte Logs** mit konfigurierbaren Log-Levels

## 📁 Dateistruktur

```
ecoflow-mqtt/
├── ecoflow_cloud_mqtt.py           # 🆕 Standalone Hauptanwendung
├── standalone_mqtt_client.py       # 🆕 MQTT Client ohne HA
├── requirements_standalone.txt     # 🆕 Standalone Dependencies
├── .env.example                    # 🆕 Konfiguration Vorlage
├── README_STANDALONE.md            # 🆕 Standalone Dokumentation
├── docker-compose.standalone.yml   # 🆕 Docker Compose
├── Dockerfile.standalone           # 🆕 Standalone Docker Image
├── mosquitto.conf                  # 🆕 MQTT Broker Config
├── start.sh                        # 🆕 Start Script
├── test_config.py                  # 🆕 Konfigurations-Tester
│
├── custom_components/ecoflow_cloud/
│   ├── __init__.py                 # 🔧 HA-Abhängigkeiten entfernt
│   ├── api/                        # ✅ Bleibt für API-Funktionalität
│   ├── devices/                    # ✅ Bleibt für Device-Support
│   └── ...
│
├── ecoflow_mqtt.py                 # ✅ Original bleibt erhalten
├── docker-compose.yml              # ✅ Original HA Version
├── README.md                       # ✅ Original Dokumentation
└── ...
```

## 🎉 Ergebnis

Sie haben jetzt **zwei getrennte Versionen**:

1. **Home Assistant Integration** - Original-Funktionalität bleibt erhalten
2. **Standalone MQTT Publisher** - Komplett unabhängig von Home Assistant

Die standalone Version kann parallel zur HA-Integration verwendet werden oder komplett eigenständig betrieben werden.
