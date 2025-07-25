# Standalone Proto Preloader ohne Home Assistant Abhängigkeiten
# Diese Datei lädt die Protocol Buffer Definitionen

try:
    from .devices.internal.proto import (
        ecopacket_pb2,  # noqa: F401 # pyright: ignore[reportUnusedImport]
        platform_pb2,  # noqa: F401 # pyright: ignore[reportUnusedImport]
        powerstream_pb2,  # noqa: F401 # pyright: ignore[reportUnusedImport]
    )
except ImportError:
    # Fallback für den Fall, dass Proto-Dateien nicht verfügbar sind
    pass
