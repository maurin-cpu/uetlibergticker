"""
Konfiguration für FlyChat Wetterdaten-System
"""

import os

# ============================================================================
# FORECAST-KONFIGURATION
# ============================================================================

# Anzahl Tage für Wettervorhersage (wird in fetch_weather.py verwendet)
# API unterstützt typischerweise bis zu 7 Tage
FORECAST_DAYS = 2

# ============================================================================
# API-KONFIGURATION
# ============================================================================

# API-Endpunkt für Wettervorhersage
API_URL = "https://api.open-meteo.com/v1/forecast"

# Wettermodell (MeteoSwiss ICON-CH Modell)
API_MODEL = "meteoswiss_icon_ch1"

# Timeout für API-Anfragen in Sekunden
API_TIMEOUT = 30

# Zeitzone für Wetterdaten
TIMEZONE = "Europe/Zurich"

# Zusätzliche API-Parameter
FORECAST_HOURS = 24  # Zusätzlicher Parameter für bessere Datenqualität
TEMPORAL_RESOLUTION = "hourly"  # 6-Stunden-Auflösung
PAST_HOURS = 1  # Vergangene Stunde einbeziehen

# ============================================================================
# DATEI-PFADE
# ============================================================================

# Pfad zur CSV-Datei mit Startplätzen (wird in fetch_weather.py verwendet)
# Die CSV-Datei sollte folgende Spalten enthalten: Name, Latitude, Longitude
CSV_FILE_PATH = os.path.join("data", "startplaetze_schweiz.csv")

# Ausgabeverzeichnis für generierte Dateien (wird in mehreren Skripten verwendet)
OUTPUT_DIR = "data"

# Name der JSON-Ausgabedatei für Wetterdaten
WEATHER_JSON_FILENAME = "wetterdaten.json"
