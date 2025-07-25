# EcoFlow Cloud MQTT Publisher (Standalone)

Ein eigenständiger MQTT Publisher für EcoFlow Geräte ohne Home Assistant Abhängigkeiten.

## 🚀 Features

- **Standalone**: Keine Home Assistant Installation erforderlich
- **MQTT Publishing**: Weiterleitung aller EcoFlow Daten per MQTT
- **Dual API Support**: Unterstützt sowohl Private API (Email/Password) als auch Public API (Access/Secret Key)
- **Multi-Device**: Überwachung mehrerer EcoFlow Geräte gleichzeitig
- **Docker Ready**: Vollständige Docker/Docker Compose Unterstützung
- **Konfigurierbar**: Flexible Konfiguration über Umgebungsvariablen

## 📋 Voraussetzungen

- Python 3.11+ (für lokale Installation)
- Docker & Docker Compose (für Container-Deployment)
- EcoFlow Account mit API-Zugang
- MQTT Broker (wird mit Docker Compose bereitgestellt)

## 🛠️ Installation

### Option 1: Docker Compose (Empfohlen)

1. **Repository klonen:**
   ```bash
   git clone <your-repo>
   cd ecoflow-mqtt
   ```

2. **Konfiguration erstellen:**
   ```bash
   cp .env.example .env
   # Bearbeiten Sie .env mit Ihren EcoFlow API Credentials
   ```

3. **Service starten:**
   ```bash
   docker-compose -f docker-compose.standalone.yml up -d
   ```

### Option 2: Lokale Python Installation

1. **Dependencies installieren:**
   ```bash
   pip install -r requirements_standalone.txt
   ```

2. **Umgebungsvariablen setzen:**
   ```bash
   export ECOFLOW_AUTH_TYPE=private
   export ECOFLOW_USERNAME=ihre-email@beispiel.de
   export ECOFLOW_PASSWORD=ihr-passwort
   export ECOFLOW_DEVICES="SN1:DEVICE_TYPE1:NAME1,SN2:DEVICE_TYPE2:NAME2"
   export MQTT_HOST=localhost
   ```

3. **Publisher starten:**
   ```bash
   python ecoflow_cloud_mqtt.py
   ```

## ⚙️ Konfiguration

### Umgebungsvariablen

| Variable | Beschreibung | Standard | Beispiel |
|----------|-------------|----------|----------|
| `ECOFLOW_AUTH_TYPE` | API Typ: `private` oder `public` | `private` | `private` |
| `ECOFLOW_USERNAME` | EcoFlow Email (für private API) | - | `user@beispiel.de` |
| `ECOFLOW_PASSWORD` | EcoFlow Passwort (für private API) | - | `meinpasswort` |
| `ECOFLOW_ACCESS_KEY` | Access Key (für public API) | - | `abcd1234...` |
| `ECOFLOW_SECRET_KEY` | Secret Key (für public API) | - | `xyz9876...` |
| `ECOFLOW_API_HOST` | EcoFlow API Host | `api.ecoflow.com` | `api.ecoflow.com` |
| `ECOFLOW_GROUP` | Geräte-Gruppe | `default` | `default` |
| `ECOFLOW_DEVICES` | Geräte-Liste (siehe unten) | - | `SN:TYPE:NAME,...` |
| `MQTT_HOST` | MQTT Broker Host | `localhost` | `mqtt.local` |
| `MQTT_PORT` | MQTT Broker Port | `1883` | `1883` |
| `MQTT_USERNAME` | MQTT Benutzername (optional) | - | `mqttuser` |
| `MQTT_PASSWORD` | MQTT Passwort (optional) | - | `mqttpass` |
| `MQTT_BASE_TOPIC` | MQTT Basis-Topic | `ecoflow` | `ecoflow` |
| `REFRESH_INTERVAL` | Abfrage-Intervall (Sekunden) | `30` | `60` |

### Geräte-Konfiguration

Die `ECOFLOW_DEVICES` Variable definiert die zu überwachenden Geräte im Format:
```
SN1:DEVICE_TYPE1:NAME1,SN2:DEVICE_TYPE2:NAME2,...
```

**Beispiel:**
```
HW52ZDH4SF270677:DELTA_2:Delta2-Garage,HW53ABC1234567:RIVER_2:River2-Wohnzimmer
```

**Unterstützte Device Types:**
- `DELTA_2`, `DELTA_PRO`, `DELTA_MAX`, `DELTA_MINI`
- `RIVER_2`, `RIVER_PRO`, `RIVER_MAX`, `RIVER_MINI`
- `POWERSTREAM`, `GLACIER`, `WAVE_2`
- Und viele mehr...

## 📊 MQTT Topics

Die Daten werden in folgender Topic-Struktur veröffentlicht:

```
ecoflow/
├── {device_sn}/
│   ├── {parameter_name}           # Einzelne Parameter
│   └── status                     # Gerätestatus-Informationen
```

**Beispiel Topics:**
```
ecoflow/HW52ZDH4SF270677/battery_level
ecoflow/HW52ZDH4SF270677/ac_out_power
ecoflow/HW52ZDH4SF270677/solar_in_power
ecoflow/HW52ZDH4SF270677/status
```

**Status-Payload Beispiel:**
```json
{
  "device_name": "Delta2-Garage",
  "device_type": "DELTA_2",
  "sn": "HW52ZDH4SF270677",
  "online": true,
  "last_update": 1698765432
}
```

## 🔧 Erweiterte Nutzung

### Mit eigenem MQTT Broker

Wenn Sie bereits einen MQTT Broker haben, können Sie den Service ohne den integrierten Broker starten:

```bash
# Nur EcoFlow Publisher ohne MQTT Broker
docker-compose -f docker-compose.standalone.yml up ecoflow-mqtt
```

### Logs anzeigen

```bash
# Docker Logs
docker-compose -f docker-compose.standalone.yml logs -f ecoflow-mqtt

# Lokale Installation
python ecoflow_cloud_mqtt.py  # Logs erscheinen auf der Konsole
```

### Service stoppen

```bash
# Docker Compose
docker-compose -f docker-compose.standalone.yml down

# Lokale Installation: Ctrl+C
```

## 🐛 Troubleshooting

### Häufige Probleme

1. **Login fehlgeschlagen:**
   - Überprüfen Sie Ihre EcoFlow Credentials
   - Stellen Sie sicher, dass der richtige `ECOFLOW_AUTH_TYPE` gesetzt ist

2. **Keine Geräte gefunden:**
   - Überprüfen Sie das Format der `ECOFLOW_DEVICES` Variable
   - Stellen Sie sicher, dass die Seriennummern korrekt sind

3. **MQTT Verbindung fehlschlägt:**
   - Prüfen Sie `MQTT_HOST` und `MQTT_PORT`
   - Überprüfen Sie Firewall-Einstellungen

4. **Import-Fehler:**
   - Installieren Sie alle Dependencies: `pip install -r requirements_standalone.txt`

### Debug-Modus aktivieren

Setzen Sie die Log-Level auf DEBUG für detailliertere Ausgaben:

```bash
export PYTHONPATH=.
python -c "
import logging
logging.basicConfig(level=logging.DEBUG)
exec(open('ecoflow_cloud_mqtt.py').read())
"
```

## 📜 Lizenz

Siehe [Haupt-README](README.md) für Lizenzinformationen.

## 🤝 Beitragen

Contributions sind willkommen! Siehe [Contribution Guidelines](docs/Contribution.md) für Details.

## ⚠️ Disclaimer

Dieses Projekt ist nicht offiziell von EcoFlow unterstützt. Verwenden Sie es auf eigene Verantwortung.
