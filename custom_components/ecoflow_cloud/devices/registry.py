from typing import Type, OrderedDict

# Verwende nur die Basis-Klassen ohne spezifische Device-Implementierungen
from ..devices import BaseDevice, DiagnosticDevice

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
        
        # Stream-Serie
        "STREAM_AC": DiagnosticDevice,
        "STREAM_MICROINVERTER": DiagnosticDevice,
        "STREAM_ULTRA": DiagnosticDevice,
        "STREAM_PRO": DiagnosticDevice,
        
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
        "Stream AC": DiagnosticDevice,
        "Stream PRO": DiagnosticDevice,
        "Stream Ultra": DiagnosticDevice,
        "Stream Microinverter": DiagnosticDevice,
        "Smart Home Panel 2": DiagnosticDevice,
        "DIAGNOSTIC": DiagnosticDevice,
    }
)

# Hilfsfunktion um Device-Klasse zu erhalten
def get_device_class(device_type: str) -> Type[BaseDevice]:
    """Gibt die Device-Klasse für den gegebenen Device-Type zurück"""
    return devices.get(device_type, DiagnosticDevice)
