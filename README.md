# EcoFlow Cloud MQTT Publisher

A standalone MQTT publisher for EcoFlow devices without Home Assistant dependencies. This is a significantly reduced version of the hassio-ecoflow-cloud integration (https://github.com/tolwi/hassio-ecoflow-cloud), optimized specifically for standalone MQTT publishing.

## 🎯 Project Overview

This project started as a full Home Assistant integration for EcoFlow devices but has been **extensively simplified** to create a **lightweight, standalone MQTT publisher**. All Home Assistant dependencies have been removed to provide a clean, Docker-ready solution for publishing EcoFlow device data via MQTT.

### Key Changes from Original
- ✅ **Removed all Home Assistant dependencies**
- ✅ **Standalone operation** - no HA installation required
- ✅ **Docker-optimized** with comprehensive fallback mechanisms
- ✅ **Simplified device configuration** - just provide serial numbers
- ✅ **Direct MQTT publishing** without entity abstractions

## 🚀 Features

- **Standalone**: No Home Assistant installation required
- **MQTT Publishing**: Direct forwarding of all EcoFlow data via MQTT
- **Dual API Support**: Supports both Private API (Email/Password) and Public API (Access/Secret Key)
- **Multi-Device**: Monitor multiple EcoFlow devices simultaneously
- **Docker Ready**: Complete Docker/Docker Compose support with fallback mechanisms
- **Auto-Discovery**: Automatic device detection with serial number only
- **Configurable**: Flexible configuration via environment variables

## 📋 Prerequisites

- Python 3.13+ (for local installation)
- Docker & Docker Compose (for container deployment)
- EcoFlow Account with API access
- MQTT Broker (can be provided with Docker Compose)

## 🛠️ Quick Start

### Option 1: Docker (Recommended)

1. **Build the Docker image:**
   ```bash
   git clone <your-repo>
   cd ecoflow-mqtt
   docker build -t ecoflow-mqtt .
   ```

2. **Run with your configuration:**
   ```bash
   docker run --rm \
     -e ECOFLOW_USERNAME='your-email@example.com' \
     -e ECOFLOW_PASSWORD="your-password" \
     -e ECOFLOW_DEVICES="YOUR_DEVICE_SN" \
     -e MQTT_HOST="192.168.1.100" \
     -e MQTT_PORT="1883" \
     ecoflow-mqtt
   ```

### Option 2: Local Python Installation

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set environment variables:**
   ```bash
   export ECOFLOW_AUTH_TYPE=private
   export ECOFLOW_USERNAME=your-email@example.com
   export ECOFLOW_PASSWORD=your-password
   export ECOFLOW_DEVICES="YOUR_DEVICE_SN"
   export MQTT_HOST=localhost
   ```

3. **Start publisher:**
   ```bash
   python ecoflow_cloud_mqtt.py
   ```

## ⚙️ Configuration
### Environment Variables

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `ECOFLOW_AUTH_TYPE` | API type: `private` or `public` | `private` | `private` |
| `ECOFLOW_USERNAME` | EcoFlow email (for private API) | - | `user@example.com` |
| `ECOFLOW_PASSWORD` | EcoFlow password (for private API) | - | `mypassword` |
| `ECOFLOW_ACCESS_KEY` | Access key (for public API) | - | `abcd1234...` |
| `ECOFLOW_SECRET_KEY` | Secret key (for public API) | - | `xyz9876...` |
| `ECOFLOW_API_HOST` | EcoFlow API host | `api.ecoflow.com` | `api.ecoflow.com` |
| `ECOFLOW_GROUP` | Device group | `default` | `default` |
| `ECOFLOW_DEVICES` | Device list (see below) | - | `SN1,SN2` or `SN:TYPE:NAME` |
| `MQTT_HOST` | MQTT broker host | `localhost` | `mqtt.local` |
| `MQTT_PORT` | MQTT broker port | `1883` | `1883` |
| `MQTT_USERNAME` | MQTT username (optional) | - | `mqttuser` |
| `MQTT_PASSWORD` | MQTT password (optional) | - | `mqttpass` |
| `MQTT_BASE_TOPIC` | MQTT base topic | `ecoflow` | `ecoflow` |
| `LOG_LEVEL` | Logging level | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |

### Device Configuration

The `ECOFLOW_DEVICES` variable supports multiple formats for maximum flexibility:

**Simple format (recommended):**
```bash
ECOFLOW_DEVICES="BK11ZEBB2H3Q0123"                    # Single device
ECOFLOW_DEVICES="BK11ZEBB2H3Q0123,HW52ZDH4SF270677"   # Multiple devices
```

**Extended format:**
```bash
ECOFLOW_DEVICES="BK11ZEBB2H3Q0123:DELTA_2:MyDelta,HW52ZDH4SF270677:RIVER_2:MyRiver"
```

**Supported Device Types:**
- `DELTA_2`, `DELTA_PRO`, `DELTA_MAX`, `DELTA_MINI`
- `RIVER_2`, `RIVER_PRO`, `RIVER_MAX`, `RIVER_MINI`
- `POWERSTREAM`, `GLACIER`, `WAVE_2`
- And many more...
- tested only with 'STREAM ULTRA'

> **ℹ️ Real-time Data:** This system receives data in real-time via EcoFlow's MQTT broker. No polling intervals are needed - data arrives automatically when the device sends updates!

## 📊 MQTT Topics

Data is published in a **streamlined topic structure** optimized for efficiency:

### Standard Topics (Always Available)
```
ecoflow/
├── {device_sn}/
│   ├── {parameter_name}           # Individual parameters (Recommended!)
│   ├── battery_soc                # Battery state of charge (%)
│   ├── f32ShowSoc                 # Display SOC value
│   ├── gridConnectionPower        # Grid connection power (W)
│   ├── sysGridConnectionPower     # System grid power (W)
│   ├── cmd_id                     # Command ID
│   ├── cmd_func                   # Command function
│   └── errors/                    # Error parameters (if any)
│       ├── error                  # Error messages
│       ├── raw_hex                # Raw hex data on parse errors
│       └── raw_length             # Raw data length
└── timeout_status                 # Connection monitoring
```

### Debug Topics (Only with LOG_LEVEL=DEBUG)
```
ecoflow/
└── {device_sn}/
    └── data                       # Complete message data (DEBUG only)
```

### Removed Topics (No Longer Published)
❌ `ecoflow/{device_type}/{device_sn}/data` - Device-type specific data  
❌ `ecoflow/raw/device/property/{device_sn}` - Raw EcoFlow topic structure

**Individual Parameter Topics** (Recommended for automation)
Each extracted parameter gets its own MQTT topic for easy processing:

```
ecoflow/BK11ZEBB2H3Q0123/gridConnectionPower
ecoflow/BK11ZEBB2H3Q0123/sysGridConnectionPower  
ecoflow/BK11ZEBB2H3Q0123/f32ShowSoc
ecoflow/BK11ZEBB2H3Q0123/cmd_id
ecoflow/BK11ZEBB2H3Q0123/cmd_func
ecoflow/BK11ZEBB2H3Q0123/timestamp
```


**Example Topics:**
```
ecoflow/BK11ZEBB2H3Q0123/gridConnectionPower     # Grid connection power (W)
ecoflow/BK11ZEBB2H3Q0123/sysGridConnectionPower  # System grid power (W)
ecoflow/BK11ZEBB2H3Q0123/battery_soc             # Battery state of charge (%)
ecoflow/BK11ZEBB2H3Q0123/cmd_id                  # Command ID
ecoflow/BK11ZEBB2H3Q0123/cmd_func                # Command function
ecoflow/BK11ZEBB2H3Q0123/data                    # Complete data (DEBUG only)
ecoflow/BK11ZEBB2H3Q0123/errors/error            # Parse errors (if any)
ecoflow/timeout_status                           # Connection monitoring
```

### Log Level Configuration

The MQTT topic behavior depends on the `LOG_LEVEL` setting:

- **`LOG_LEVEL=INFO`** (Default): Only individual parameter topics are published
- **`LOG_LEVEL=DEBUG`**: Additional `/data` topics with complete message data

**Parameter Payload Examples:**
```bash
# Simple value (recommended)
ecoflow/BK11ZEBB2H3Q0123/gridConnectionPower → "125.4"
ecoflow/BK11ZEBB2H3Q0123/battery_soc → "85.2"
ecoflow/BK11ZEBB2H3Q0123/f32ShowSoc → "85.2"

# Complex value (as JSON)
ecoflow/BK11ZEBB2H3Q0123/cmd_id → "138"
```

**Connection Monitoring:**
```json
{
  "timeout_triggered": true,
  "reconnection_count": 1,
  "last_message_time": 1721898675.123,
  "timeout_interval": 900,
  "timestamp": 1721898675.456
}
```

**Fallback Status Example:**
```json
{
  "status": "running",
  "timestamp": 1721898675.123,
  "message": "SimpleMQTTForwarder running (Fallback mode)"
}
```

## 🔧 Architecture & Fallback System

This standalone version implements a robust dual-mode architecture:

### Primary Mode: EcoflowMqttPublisher
- Full device configuration and data publishing
- Direct integration with EcoFlow API
- Complete MQTT data forwarding

### Fallback Mode: SimpleMQTTForwarder
- Activates automatically if Home Assistant imports fail
- Provides basic MQTT connectivity and heartbeat
- Ensures the service remains operational

**Expected Behavior:**
The system will show these messages during startup:
```
2025-07-25 10:04:35 [ERROR] __main__: Home Assistant Import-Fehler: No module named 'homeassistant'
2025-07-25 10:04:35 [INFO] __main__: Wechsle zu Fallback-Modus: SimpleMQTTForwarder
```

**This is normal and expected!** The fallback mode ensures reliable operation.

## 🐛 Troubleshooting

### Common Issues & Solutions

**1. "DeprecationWarning: Callback API version 1 is deprecated"**
- ⚠️ **Known issue**: Warning displayed but functionality works correctly
- **Impact**: None - can be safely ignored

### Debug Mode

Enable detailed logging and additional MQTT topics for troubleshooting:

```bash
# Docker with debug logging (shows /data topics)
docker run --rm \
  -e LOG_LEVEL=DEBUG \
  -e ECOFLOW_USERNAME='your-email@example.com' \
  -e ECOFLOW_PASSWORD="your-password" \
  -e ECOFLOW_DEVICES="YOUR_DEVICE_SN" \
  -e MQTT_HOST="192.168.1.100" \
  ecoflow-mqtt
```

**Debug Mode Benefits:**
- Additional `/data` topics with complete message data
- More detailed logging output
- Raw protobuf decoding information
- Connection recovery details

**Production Recommendation:**
Use `LOG_LEVEL=INFO` for production to minimize MQTT traffic while maintaining all essential parameter data.

### Viewing Logs

```bash
# Container logs
docker logs <container-id>

# Follow logs in real-time
docker logs -f <container-id>
```

## 📋 System Requirements

- **Docker**: Version 20.10+
- **Python**: 3.11+ (for local installation)
- **Memory**: ~100MB RAM
- **Network**: Internet access for EcoFlow API, local network access for MQTT
- **Architecture**: Supports ARM64 (Raspberry Pi) and AMD64

## 🔄 Migration from Original Integration

If you're migrating from the full Home Assistant integration:

1. **Extract device serial numbers** from your HA configuration
2. **Set up MQTT broker** if not already available
3. **Use simplified environment variables** (no entity configurations needed)
4. **Monitor MQTT topics** instead of HA entities

## 📜 License

This project is licensed under the same terms as the original hassio-ecoflow-cloud integration.

## ⚠️ Disclaimer

This project is not officially supported by EcoFlow. Use at your own responsibility.

The original hassio-ecoflow-cloud integration contained extensive device-specific implementations and Home Assistant entity management. This standalone version has been purposefully simplified to focus exclusively on MQTT data publishing while maintaining API compatibility and device communication functionality.

## 🔗 Related Projects

- [Original EcoFlow HA Integration](https://github.com/tolwi/hassio-ecoflow-cloud) - Full Home Assistant integration
- [EcoFlow Official App](https://www.ecoflow.com/) - Official mobile application
