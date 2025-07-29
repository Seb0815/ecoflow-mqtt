from typing import Type, OrderedDict
import logging

# Verwende sowohl Basis-Klassen als auch spezifische Device-Implementierungen
from ..devices import BaseDevice, DiagnosticDevice

_LOGGER = logging.getLogger(__name__)

# Import der spezifischen Device-Klassen für korrekte Dateninterpretation
try:
    from .internal.stream_ac import StreamAC
    _LOGGER.info("✅ StreamAC class imported successfully")
except ImportError as e:
    _LOGGER.warning(f"⚠️ Could not import StreamAC: {e}")
    StreamAC = DiagnosticDevice

# Fallback-Dictionary für unterstützte Geräte
# Da wir nur MQTT Publishing brauchen, verwenden wir DiagnosticDevice für alle Typen
devices: OrderedDict[str, Type[BaseDevice]] = OrderedDict[str, Type[BaseDevice]](
    {
        # Delta-Serie
        "DELTA_2": DiagnosticDevice,
        "DELTA_2_MAX": DiagnosticDevice,
        "DELTA_PRO": DiagnosticDevice,
        "DELTA_MAX": DiagnosticDevice,
        "DELTA_MINI": DiagnosticDevice,
        "DELTA_PRO_3": DiagnosticDevice,
        
        # River-Serie
        "RIVER_2": DiagnosticDevice,
        "RIVER_2_MAX": DiagnosticDevice,
        "RIVER_2_PRO": DiagnosticDevice,
        "RIVER_MAX": DiagnosticDevice,
        "RIVER_PRO": DiagnosticDevice,
        "RIVER_MINI": DiagnosticDevice,
        
        # PowerStream
        "HW52_7S11P": DiagnosticDevice,  # PowerStream
        "POWERSTREAM": DiagnosticDevice,
        
        # Wave-Serie
        "WAVE_2": DiagnosticDevice,
        
        # Glacier
        "BX11_1222": DiagnosticDevice,  # Glacier
        "GLACIER": DiagnosticDevice,
        
        # Smart Home
        "SMART_METER": DiagnosticDevice,
        "SMART_PLUG": DiagnosticDevice,
        "SMART_HOME_PANEL_2": DiagnosticDevice,
        
        # Stream-Serie - Verwende spezifische StreamAC-Klasse!
        "STREAM_AC": StreamAC,
        "STREAM_ULTRA": StreamAC,  # Stream Ultra verwendet StreamAC-Parsing
        "STREAM_PRO": StreamAC,
        "STREAM_MICROINVERTER": DiagnosticDevice,
        
        # Power Kits
        "POWER_KITS": DiagnosticDevice,
        
        # Diagnostic fallback
        "DIAGNOSTIC": DiagnosticDevice,
    }
)

public_devices: OrderedDict[str, Type[BaseDevice]] = devices.copy()

device_by_product: OrderedDict[str, Type[BaseDevice]] = OrderedDict[str, Type[BaseDevice]](
    {
        "DELTA Max": DiagnosticDevice,
        "DELTA Pro": DiagnosticDevice,
        "DELTA 2": DiagnosticDevice,
        "DELTA 2 Max": DiagnosticDevice,
        "RIVER 2": DiagnosticDevice,
        "RIVER 2 Max": DiagnosticDevice,
        "RIVER 2 Pro": DiagnosticDevice,
        "Smart Plug": DiagnosticDevice,
        "PowerStream": DiagnosticDevice,
        "WAVE 2": DiagnosticDevice,
        "Delta Pro 3": DiagnosticDevice,
        "Power Kits": DiagnosticDevice,
        "Smart Meter": DiagnosticDevice,
        "Stream AC": StreamAC,
        "Stream PRO": StreamAC,
        "Stream Ultra": StreamAC,  # Stream Ultra verwendet StreamAC-Parsing
        "Stream Microinverter": DiagnosticDevice,
        "Smart Home Panel 2": DiagnosticDevice,
        "DIAGNOSTIC": DiagnosticDevice,
    }
)

# Hilfsfunktion um Device-Klasse zu erhalten
def get_device_class(device_type: str) -> Type[BaseDevice]:
    """Gibt die Device-Klasse für den gegebenen Device-Type zurück"""
    return devices.get(device_type, DiagnosticDevice)
