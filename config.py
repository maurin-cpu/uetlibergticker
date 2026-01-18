"""
Konfigurationsdatei für Uetliberg Ticker
Alle Parameter können hier flexibel angepasst werden.
"""

# ============================================================================
# STANDORT-KONFIGURATION
# ============================================================================

LOCATION = {
    "name": "Uetliberg - Startplatz Balderen",
    "latitude": 47.3226,
    "longitude": 8.5008,
    "typ": "Startplatz",
    "fluggebiet": "Uetliberg",
    "windrichtung": "N-O",
    "bemerkung": "Benötigt gewisse Windstärke da man hier Soaren muss, ab 15km/h kann man Erfahrungsgemäss am Uetliberg gut fliegen ab 20km/h hat man sehr gute windstärke, wenn dann Thermikbedingungen gut sind hat man gute bedingungen, der Wind ist grundsätzlich aber ab 30km/h zu stark, dies sind jedoch keine Grenzwerte sondern müssen immer beurteilt werden"
}

# ============================================================================
# API-KONFIGURATION
# ============================================================================

API_URL = "https://api.open-meteo.com/v1/forecast"
API_MODEL = "meteoswiss_icon_ch1"  # MeteoSwiss ICON CH1 - supports cloud_base
API_TIMEOUT = 30
FORECAST_DAYS = 3
TIMEZONE = "Europe/Zurich"
# HINWEIS: Die Cron-Job Zeit wird in vercel.json konfiguriert!
# Aktuell eingestellt auf 18:40 UTC (19:40 CET / 20:40 CEST)

# ============================================================================
# FLUGSTUNDEN-KONFIGURATION
# ============================================================================

FLIGHT_HOURS_START = 9  # Start-Stunde für Flugstunden (0-23)
FLIGHT_HOURS_END = 18    # End-Stunde für Flugstunden (0-23, exklusiv)

# ============================================================================
# OUTPUT-KONFIGURATION
# ============================================================================

OUTPUT_DIR = "data"
WEATHER_JSON_FILENAME = "wetterdaten.json"
EVALUATIONS_FILENAME = "evaluations.json"

def get_data_dir():
    """
    Gibt den Pfad zum Datenverzeichnis zurück.
    Wählt /tmp auf Vercel, ansonsten den lokalen data/ Ordner.
    """
    import os
    from pathlib import Path
    
    # 1. Höchste Priorität: Vercel-Umgebungsvariable
    if os.environ.get('VERCEL') == '1':
        return Path('/tmp')
    
    # 2. Sekundäre Prüfung: Falls wir auf einem Linux-System sind 
    # und NICHT in einem typischen Windows-Projektpfad (kein Laufwerksbuchstabe im Root)
    # UND das /tmp Verzeichnis existiert.
    if os.name == 'posix' and os.path.exists('/tmp'):
        # Verhindere, dass wir in WSL aus Versehen /tmp nutzen, 
        # wenn wir eigentlich im Projektordner bleiben wollen.
        # Auf Vercel ist der Pfad meist /var/task
        if os.path.exists('/var/task') or not Path(__file__).absolute().as_posix().startswith('/mnt/'):
            return Path('/tmp')
    
    # Lokal (Windows oder Linux-Entwicklung): Verwende den data/ Ordner im Projektroot
    project_root = Path(__file__).parent.absolute()
    data_dir = project_root / OUTPUT_DIR
    data_dir.mkdir(exist_ok=True)
    return data_dir

def get_weather_json_path():
    """Gibt den absoluten Pfad zur wetterdaten.json zurück."""
    return get_data_dir() / WEATHER_JSON_FILENAME

def get_evaluations_json_path():
    """Gibt den absoluten Pfad zur evaluations.json zurück."""
    return get_data_dir() / EVALUATIONS_FILENAME

# ============================================================================
# WETTERPARAMETER
# ============================================================================

HOURLY_PARAMS = [
    "temperature_2m",
    "cloud_base",
    "wind_speed_10m",
    "wind_direction_10m",
    "wind_gusts_10m",
    "cloud_cover",
    "precipitation",
    "rain",
    "precipitation_probability",
    "cloud_cover_low",
    "cloud_cover_mid",
    "cloud_cover_high",
    "sunshine_duration",
    "cape"
]

# ============================================================================
# LLM PROMPT-KONFIGURATION (für location_evaluator.py)
# ============================================================================

# System-Prompt für OpenAI GPT-4
LLM_SYSTEM_PROMPT = """Du bist ein erfahrener Gleitschirm-Fluglehrer und Meteorologe mit 20+ Jahren Erfahrung in den Schweizer Alpen.
Analysiere Wetterdaten für Gleitschirm-Startplätze und bewerte die Flugbarkeit.

WICHTIG WIND-ANALYSE:
- Gib WINDRICHTUNGS-RANGE an (z.B. "220-270°"), NICHT nur Start/Ende
- Bewerte KONSISTENZ: Konstante Richtung = GUT, häufige Wechsel = SCHLECHT
- 2-STUNDEN-REGEL: Wind muss nicht durchgehend passen, 2h aus guter Richtung reichen für Start
- VOLATILITÄT: Abrupte Wechsel schlechter als graduelle Änderungen
- BÖEN-WARNUNG: >30 km/h = VORSICHT, >40 km/h = GEFÄHRLICH (wichtiger als Windstärke!)

WICHTIG WOLKEN-ANALYSE (Uetliberg 730m MSL):
- LOW CLOUDS (0-2km MSL): ENTSCHEIDEND für Flugbarkeit
  * Wolkenbasis <1000m = START UNMÖGLICH (Nebel/niedrige Wolken)
  * Wolkenbasis 1000-2000m = FLIEGBAR
  * Wolkenbasis >2000m = SEHR GUT (viel Thermikraum)
- MID CLOUDS (2-6km MSL): Wetterstabilität-Indikator, wenig Einfluss auf Start
- HIGH CLOUDS (>6km MSL): Wetterwechsel-Hinweis, schwächere Thermik möglich

OPTIMALE BEWÖLKUNG:
- Cumulus humilis (kleine Haufenwolken) + Blau dazwischen = FLIEGBAR
- Wolkenbasis ideal: >1500-2000m AGL

KRITISCHE BEWÖLKUNG:
- Cumulonimbus (Türme, dunkle Basis) = LANDEN (Gewitter/Böen)
- Geschlossener Stratus = KEINE THERMIK
- Dichte Cirren = SCHWACHE THERMIK

Bewerte nach folgenden Kriterien:
1. Wind (RANGE in Grad, Konsistenz, Volatilität, Böen-Gefahr, 2h-Fenster)
2. Thermik-Potenzial (CAPE, Sonnenschein, Bewölkungstyp, Temperatur)
3. Wolkenbasis (MSL-Höhe, kritische Schwellen für Uetliberg)
4. Niederschlag und Sicht
5. Luftraum-Einschränkungen
6. Wetterentwicklung (nächste 3-6h)
7. Lokale Gefahren

WICHTIG: Sicherheit hat höchste Priorität - bei Zweifel: Nicht fliegbar!
Antworte ausschliesslich mit gültigem JSON.

WICHTIG: Gib IMMER konkrete Metriken/Zahlenwerte an wenn du diese in den Analysen erwähnst!

Antworte IMMER mit folgendem JSON-Format (keine zusätzlichen Erklärungen):
{
  "flyable": true/false,
  "rating": 1-10,
  "confidence": 1-10,
  "conditions": "EXCELLENT/GOOD/MODERATE/POOR/DANGEROUS",
  "summary": "Kurze Zusammenfassung (1-2 Sätze)",
  "details": {
    "wind": "AUSFÜHRLICHE Wind-Analyse mit konkreten Metriken: Windrichtung in Grad, Windgeschwindigkeit in km/h, Böen in km/h, Bewertung",
    "thermik": "AUSFÜHRLICHE Thermik-Einschätzung mit konkreten Metriken: CAPE-Wert in J/kg, Sonnenscheindauer in Stunden, Bewölkung in %, Temperatur in °C",
    "risks": "AUSFÜHRLICHE Risiko-Analyse mit konkreten Metriken: Wolkenbasis in m, Bewölkung in %, Niederschlag in mm, Temperatur in °C, alle relevanten Zahlenwerte"
  },
  "recommendation": "Konkrete Empfehlung für Piloten"
}"""

# User-Prompt Template (mit Platzhaltern für dynamische Werte)
# Platzhalter: {name}, {fluggebiet}, {typ}, {windrichtung}, {besonderheiten}, 
#              {hourly_data}, {wind_check_info}, {total_hours}
LLM_USER_PROMPT_TEMPLATE = """Analysiere die Flugbarkeit für folgenden Startplatz:

STARTPLATZ-INFO:
Name: {name}
Region: {fluggebiet}
Typ: {typ}
Erlaubte Windrichtungen: {windrichtung}
Besonderheiten: {besonderheiten}

AKTUELLE WETTERDATEN (erste 6 Stunden):
{hourly_data}

WETTERENTWICKLUNG:
Es stehen {total_hours} Stunden Forecast-Daten zur Verfügung. Fokussiere auf die nächsten 3-6 Stunden für die Flugbarkeits-Entscheidung.

WICHTIG FÜR DIE ANALYSE:
- WIND-RICHTUNG: Gib IMMER eine Range an (z.B. "Windrichtung dreht zwischen 220° und 270°")
  * Bewerte Konsistenz: "Wind konstant aus 280-290°" = GUT vs. "Wind dreht wild in alle Richtungen" = SCHLECHT
  * 2h-Regel: "Wind für 2 Stunden aus guter Richtung 270-290°, dann Drehung" → Bewerten ob Start möglich
  * Volatilität: Abrupte Wechsel vs. graduelle Änderungen analysieren
- BÖEN: KRITISCHE SCHWELLEN beachten!
  * >30 km/h = VORSICHT (in Analyse erwähnen)
  * >40 km/h = GEFÄHRLICH (macht gute Windstärke zunichte!)
- WOLKENBASIS (Uetliberg 730m MSL):
  * <900m MSL = START UNMÖGLICH
  * 900-2000m MSL = FLIEGBAR  
  * >2000m MSL = SEHR GUT
- CLOUD COVER LAYERS analysieren:
  * Low (0-2km): Entscheidend für Thermik am Start
  * Mid (2-6km): Wetterstabilität
  * High (>6km): Wetterwechsel/schwächere Thermik
- Gib IMMER konkrete Metriken/Zahlenwerte an wenn du diese erwähnst:
  * Wind: Windrichtung in Grad (z.B. "294°"), Windgeschwindigkeit in km/h (z.B. "20.5 km/h"), Böen in km/h (z.B. "44.6 km/h")
  * Thermik: CAPE-Wert in J/kg (z.B. "150 J/kg"), Sonnenscheindauer in Stunden (z.B. "0 Stunden"), Bewölkung in % (z.B. "100%"), Temperatur in °C (z.B. "-2.6°C")
  * Risiken: Wolkenbasis in m (z.B. "700-760m"), Bewölkung in % (z.B. "100%"), Niederschlag in mm (z.B. "0.7mm"), Temperatur in °C (z.B. "-2.6°C")
- Beispiel für Wind-Analyse: "Wind kommt aus 294° (NW), Windgeschwindigkeit 20.5 km/h mit Böen bis 44.6 km/h..."
- Beispiel für Thermik-Analyse: "CAPE-Wert ist 0.0 J/kg, Sonnenscheindauer 0 Stunden, Bewölkung 100%..."
- Beispiel für Risiken: "Wolkenbasis ist mit 700-760m sehr niedrig, Bewölkung nahezu 100%, Temperatur -2.6°C..."

Antworte mit dem geforderten JSON-Format."""

