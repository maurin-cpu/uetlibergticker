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
API_MODEL = "best_match"
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

WICHTIG: 
- Sicherheit hat höchste Priorität
- Bei Zweifel: Nicht fliegbar
- Berücksichtige lokale Besonderheiten (Luftraum, Topografie)
- CAPE-Werte sind wichtig für Thermik-Einschätzung (>500 J/kg = gut, 200-500 = moderat, <200 = schwach)
- Wolkenbasis (cloud_base) wichtig für Flughöhe
- Antworte ausschliesslich mit gültigem JSON

Bewerte nach folgenden Kriterien:
1. Wind (Richtung in Grad, Stärke in km/h, Böen in km/h, Passt zur erlaubten Startrichtung?)
2. Thermik-Potenzial (CAPE in J/kg, Sonnenscheindauer in Stunden, Bewölkung in %, Temperatur in °C)
3. Wolkenbasis und Flughöhe (Wolkenbasis in Metern)
4. Niederschlag und Sicht (Niederschlag in mm, Bewölkung in %)
5. Luftraum-Einschränkungen (aus Bemerkungen)
6. Wetterentwicklung (nächste 3-6h)
7. Lokale Gefahren (Rotoren, Lee, etc.)

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

HINWEISE: 
- Nutze CAPE-Werte für Thermik-Bewertung (>500 J/kg = gute Thermik, 200-500 = moderat, <200 = schwach)
- Berücksichtige Wolkenbasis für maximale Flughöhe
- Prüfe ob Wind aus erlaubter Richtung kommt (siehe erlaubte Windrichtungen oben)
- Beachte lokale Besonderheiten aus den Bemerkungen
- Bei Unsicherheit: Sicherheitshalber als nicht fliegbar bewerten

WICHTIG FÜR DIE ANALYSE:
- Gib IMMER konkrete Metriken/Zahlenwerte an wenn du diese erwähnst:
  * Wind: Windrichtung in Grad (z.B. "294°"), Windgeschwindigkeit in km/h (z.B. "20.5 km/h"), Böen in km/h (z.B. "44.6 km/h")
  * Thermik: CAPE-Wert in J/kg (z.B. "150 J/kg"), Sonnenscheindauer in Stunden (z.B. "0 Stunden"), Bewölkung in % (z.B. "100%"), Temperatur in °C (z.B. "-2.6°C")
  * Risiken: Wolkenbasis in m (z.B. "700-760m"), Bewölkung in % (z.B. "100%"), Niederschlag in mm (z.B. "0.7mm"), Temperatur in °C (z.B. "-2.6°C")
- Beispiel für Wind-Analyse: "Wind kommt aus 294° (NW), Windgeschwindigkeit 20.5 km/h mit Böen bis 44.6 km/h..."
- Beispiel für Thermik-Analyse: "CAPE-Wert ist 0.0 J/kg, Sonnenscheindauer 0 Stunden, Bewölkung 100%..."
- Beispiel für Risiken: "Wolkenbasis ist mit 700-760m sehr niedrig, Bewölkung nahezu 100%, Temperatur -2.6°C..."

Antworte mit dem geforderten JSON-Format."""

