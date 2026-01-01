"""
Konfiguration für MeteoSwiss Wetterdaten Aggregator
"""

from datetime import datetime, timedelta

# Wichtige Schweizer Standorte mit Koordinaten
# Format: {"name": (latitude, longitude)}
SWISS_LOCATIONS = {
    "Zürich": (47.3769, 8.5417),
    "Bern": (46.9481, 7.4474),
    "Genf": (46.2044, 6.1432),
    "Basel": (47.5596, 7.5886),
    "Lausanne": (46.5197, 6.6323),
    "Luzern": (47.0502, 8.3093),
    "St. Gallen": (47.4245, 9.3767),
    "Lugano": (46.0037, 8.9511),
    "Sion": (46.2292, 7.3604),
    "Chur": (46.8499, 9.5329),
    "Payerne": (46.8206, 6.9361),
    "Samedan": (46.5333, 9.8833),
}

# Wichtige Schweizer Wetterstationen (für Kompatibilität)
WEATHER_STATIONS = list(SWISS_LOCATIONS.keys())

# Variablen-Mapping für MeteoSwiss
# Diese Variablen entsprechen den verfügbaren Parametern in MeteoSwiss Open Data
VARIABLES = {
    "temperature": "temperature",  # Temperatur in °C
    "wind_direction": "wind_direction",  # Windrichtung in Grad
    "wind_speed": "wind_speed",  # Windstärke in m/s oder km/h
    "cloud_height": "cloud_base_height",  # Höhe der Bewölkung in m
}

# Anzahl Tage in die Zukunft für Wettervorhersage (API unterstützt bis zu 7 Tage)
DEFAULT_DAYS_FORWARD = 7

def get_forward_date_range(days_forward=None):
    """
    Gibt den Datumsbereich für den Datenabruf zurück (heute bis X Tage in die Zukunft).
    
    Args:
        days_forward: Anzahl Tage in die Zukunft (Standard: DEFAULT_DAYS_FORWARD)
    
    Returns:
        Tuple von (start_date, end_date) als datetime Objekte
    """
    if days_forward is None:
        days_forward = DEFAULT_DAYS_FORWARD
    
    start_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    end_date = start_date + timedelta(days=days_forward)
    
    return start_date, end_date

# CSV-Ausgabepfad
OUTPUT_DIR = "data"
OUTPUT_FILENAME = "wetterdaten.csv"

def get_output_path():
    """Gibt den vollständigen Pfad zur CSV-Ausgabedatei zurück."""
    return f"{OUTPUT_DIR}/{OUTPUT_FILENAME}"

