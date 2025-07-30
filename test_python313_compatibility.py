#!/usr/bin/env python3
"""
Python 3.13 Kompatibilitäts-Test für EcoFlow MQTT Bridge
Prüft auf bekannte Inkompatibilitäten mit Python 3.13
"""

import sys
import importlib
import traceback

def test_python_version():
    """Test Python Version"""
    print(f"Python Version: {sys.version}")
    
    # Prüfe Python 3.13+ Funktionen
    if sys.version_info >= (3, 13):
        print("✅ Python 3.13+ erkannt")
        
        # Test deprecated Funktionen
        try:
            import asyncio
            # asyncio.get_event_loop() sollte nicht mehr verwendet werden
            print("✅ asyncio importiert erfolgreich")
        except Exception as e:
            print(f"❌ asyncio Import fehlgeschlagen: {e}")
    else:
        print(f"⚠️  Python {sys.version_info.major}.{sys.version_info.minor} - empfohlen 3.13+")

def test_imports():
    """Test kritische Imports"""
    critical_imports = [
        'asyncio',
        'json', 
        'logging',
        'typing',
        'datetime',
        'time',
        'struct'
    ]
    
    print("\n=== KRITISCHE IMPORTS ===")
    for module_name in critical_imports:
        try:
            importlib.import_module(module_name)
            print(f"✅ {module_name}")
        except ImportError as e:
            print(f"❌ {module_name}: {e}")

def test_typing_features():
    """Test Typing Features für Python 3.13"""
    print("\n=== TYPING FEATURES ===")
    
    # Test override decorator
    try:
        from typing import override
        print("✅ typing.override verfügbar (Python 3.12+)")
    except ImportError:
        print("⚠️  typing.override nicht verfügbar - Fallback erforderlich")
    
    # Test Dict vs dict
    try:
        from typing import Dict
        print("✅ typing.Dict verfügbar (aber deprecated)")
    except ImportError:
        print("❌ typing.Dict nicht verfügbar")
    
    # Test moderne dict annotation
    try:
        test_dict: dict[str, int] = {"test": 1}
        print("✅ dict[str, int] Annotation funktioniert")
    except Exception as e:
        print(f"❌ dict[str, int] Annotation fehlgeschlagen: {e}")

def test_datetime_features():
    """Test DateTime Features für Python 3.13"""
    print("\n=== DATETIME FEATURES ===")
    
    import datetime
    
    # Test deprecated datetime.utcnow()
    try:
        import warnings
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            dt = datetime.datetime.utcnow()
            if w and any("deprecated" in str(warning.message).lower() for warning in w):
                print("⚠️  datetime.utcnow() ist deprecated - UTC Ersatz verwenden")
            else:
                print("✅ datetime.utcnow() funktioniert (noch)")
    except Exception as e:
        print(f"❌ datetime.utcnow() fehlgeschlagen: {e}")
    
    # Test moderne UTC Lösung
    try:
        dt = datetime.datetime.now(datetime.timezone.utc)
        print("✅ datetime.now(timezone.utc) funktioniert")
    except Exception as e:
        print(f"❌ datetime.now(timezone.utc) fehlgeschlagen: {e}")

def test_asyncio_features():
    """Test AsyncIO Features für Python 3.13"""
    print("\n=== ASYNCIO FEATURES ===")
    
    import asyncio
    
    # Test deprecated get_event_loop()
    try:
        import warnings
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            loop = asyncio.get_event_loop()
            if w and any("deprecated" in str(warning.message).lower() for warning in w):
                print("⚠️  asyncio.get_event_loop() ist deprecated - get_running_loop() verwenden")
            else:
                print("✅ asyncio.get_event_loop() funktioniert (noch)")
    except Exception as e:
        print(f"❌ asyncio.get_event_loop() fehlgeschlagen: {e}")
    
    # Test moderne Lösung
    async def test_running_loop():
        try:
            loop = asyncio.get_running_loop()
            return "✅ asyncio.get_running_loop() funktioniert"
        except Exception as e:
            return f"❌ asyncio.get_running_loop() fehlgeschlagen: {e}"
    
    try:
        result = asyncio.run(test_running_loop())
        print(result)
    except Exception as e:
        print(f"❌ AsyncIO Test fehlgeschlagen: {e}")

def test_protobuf_compatibility():
    """Test Protobuf Kompatibilität"""
    print("\n=== PROTOBUF COMPATIBILITY ===")
    
    try:
        import google.protobuf
        print(f"✅ Protobuf verfügbar: Version {google.protobuf.__version__}")
        
        # Test basic protobuf functionality
        from google.protobuf.message import Message
        print("✅ Protobuf Message Import erfolgreich")
        
    except ImportError as e:
        print(f"❌ Protobuf nicht verfügbar: {e}")

def test_ecoflow_imports():
    """Test EcoFlow spezifische Imports"""
    print("\n=== ECOFLOW IMPORTS ===")
    
    try:
        # Test ob unsere Custom Components importiert werden können
        import custom_components.ecoflow_cloud.api.private_api
        print("✅ EcoFlow Private API importierbar")
    except ImportError as e:
        print(f"❌ EcoFlow Private API Import fehlgeschlagen: {e}")
        print(f"   Details: {traceback.format_exc()}")

def main():
    """Haupt-Test-Funktion"""
    print("=== PYTHON 3.13 KOMPATIBILITÄTS-TEST ===")
    print("Testet die EcoFlow MQTT Bridge auf Python 3.13 Kompatibilität\n")
    
    test_python_version()
    test_imports()
    test_typing_features()
    test_datetime_features()
    test_asyncio_features()
    test_protobuf_compatibility()
    test_ecoflow_imports()
    
    print("\n=== TEST ABGESCHLOSSEN ===")
    print("Wenn alle Tests ✅ sind, sollte die Bridge mit Python 3.13 funktionieren")
    print("Bei ⚠️  Warnungen sind Fallbacks implementiert")
    print("Bei ❌ Fehlern müssen Dependencies installiert oder Code angepasst werden")

if __name__ == "__main__":
    main()
