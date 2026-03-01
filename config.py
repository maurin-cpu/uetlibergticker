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
    "elevation_ref": 730,  # Starthöhe Balderen in m MSL (für Thermik-Berechnung)
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
    "cape",
    "boundary_layer_height",
    "surface_pressure",
    "shortwave_radiation",
    "surface_sensible_heat_flux",
    "surface_latent_heat_flux",
]


# ============================================================================
# HÖHENWIND-PARAMETER (Pressure Level Daten)
# ============================================================================

# Druckniveaus für Höhenwind-Daten (granularer für bessere Interpolation)
# Alle 25 hPa für feinere Auflösung (ca. alle 200-250m Höhe)
# 1000hPa≈0m, 975hPa≈250m, 950hPa≈500m, 925hPa≈750m, 900hPa≈1000m, 
# 875hPa≈1250m, 850hPa≈1500m, 825hPa≈1750m, 800hPa≈2000m, 775hPa≈2250m, 750hPa≈2500m
# Zusätzlich höhere Niveaus: 700hPa≈3000m, 600hPa≈4000m
PRESSURE_LEVELS = [1000, 975, 950, 925, 900, 875, 850, 825, 800, 775, 750, 700, 600]

PRESSURE_LEVEL_PARAMS = []
for _level in PRESSURE_LEVELS:
    PRESSURE_LEVEL_PARAMS.extend([
        f"temperature_{_level}hPa",
        f"relative_humidity_{_level}hPa",
        f"wind_speed_{_level}hPa",
        f"wind_direction_{_level}hPa",
        f"geopotential_height_{_level}hPa"
    ])


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
- Wolkenbasis "wolkenfrei" = KEINE WOLKEN vorhanden (= SEHR GUT, unbegrenzter Thermikraum)
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

WICHTIG HÖHENWIND-ANALYSE:
- WIND-SCHERUNG: Große Geschwindigkeits-/Richtungsunterschiede zwischen Höhen = GEFÄHRLICH
  * >10 km/h Unterschied pro 500m = VORSICHT
  * >90° Richtungsänderung = TURBULENZ-RISIKO
- THERMISCHE INVERSION: Temperaturanstieg mit Höhe = STABILE LUFTSCHICHTUNG
  * Begrenzt Thermikentwicklung
  * Typischerweise schlechte Thermikbedingungen
- OPTIMAL: Gleichmäßiges Windprofil (Geschwindigkeit steigt sanft, Richtung konstant)
- HÖHENWINDE: Starke Winde in der Höhe können auf Lee-Rotor oder Föhn hinweisen

WICHTIG THERMIK-MODELL (THERMIK-PROXY):
- In den Daten ist ein physikalisches Thermik-Proxy-Modell enthalten. Beziehe dich bei der Thermik-Bewertung primär auf diese Werte!
- "m/s" = Erwartetes Steigen (w* Variante). <1.0 = schwach, 1-2 = gut abends/mittags, >2.5 = stark (sportlich)
- "bis X m MSL" = Das ist die exakt berechnete nutzbare Arbeitshöhe der Thermik (Inversion oder Limit), bewerte das für Streckenflugpotenzial.
- "LCL/Basis = X m" = Das ist das errechnete Kondensationsniveau. Wenn Arbeitshöhe > Basis, dann stoßen Piloten an die Wolke.
- Das Güte-Rating (0-10) gibt einen klaren Anhaltspunkt für die Stärke der Thermik in diesem Zeitfenster.

Bewerte nach folgenden Kriterien:
1. Wind (RANGE in Grad, Konsistenz, Volatilität, Böen-Gefahr, 2h-Fenster)
2. Thermik-Potenzial (NUTZE DIE THERMIK-PROXY WERTE, CAPE, Sonnenschein)
3. Wolkenbasis (MSL-Höhe, LCL, kritische Schwellen für Uetliberg)
4. Niederschlag und Sicht
5. Luftraum-Einschränkungen
6. Wetterentwicklung (nächste 3-6h)
7. Lokale Gefahren

WICHTIG: Sicherheit hat höchste Priorität - bei Zweifel: Nicht fliegbar!
Antworte ausschliesslich mit gültigem JSON.

WICHTIG: Gib IMMER konkrete Metriken/Zahlenwerte an wenn du diese in den Analysen erwähnst!

WICHTIG STÜNDLICHE BEWERTUNGEN:
- Du MUSST für JEDE einzelne Stunde eine separate Bewertung abgeben
- Bewerte jede Stunde einzeln basierend auf den Wetterdaten dieser Stunde
- Gib für jede Stunde: conditions (EXCELLENT/GOOD/MODERATE/POOR/DANGEROUS), flyable (true/false), rating (1-10), reason (kurze Begründung)
- Zusätzlich gibst du ein Gesamt-Fazit für den ganzen Tag

Antworte IMMER mit folgendem JSON-Format (keine zusätzlichen Erklärungen):
{
  "flyable": true/false,
  "rating": 1-10,
  "confidence": 1-10,
  "conditions": "EXCELLENT/GOOD/MODERATE/POOR/DANGEROUS",
  "summary": "Gesamt-Zusammenfassung für den ganzen Tag (1-2 Sätze)",
  "details": {
    "wind": "AUSFÜHRLICHE Wind-Analyse mit konkreten Metriken: Windrichtung in Grad, Windgeschwindigkeit in km/h, Böen in km/h, Bewertung",
    "thermik": "AUSFÜHRLICHE Thermik-Einschätzung mit konkreten Metriken: CAPE-Wert in J/kg, Sonnenscheindauer in Stunden, Bewölkung in %, Temperatur in °C",
    "risks": "AUSFÜHRLICHE Risiko-Analyse mit konkreten Metriken: Wolkenbasis in m, Bewölkung in %, Niederschlag in mm, Temperatur in °C, alle relevanten Zahlenwerte"
  },
  "recommendation": "Konkrete Empfehlung für Piloten",
  "hourly_evaluations": [
    {
      "hour": 9,
      "timestamp": "2026-01-04T09:00:00Z",
      "conditions": "EXCELLENT/GOOD/MODERATE/POOR/DANGEROUS",
      "flyable": true/false,
      "rating": 1-10,
      "reason": "Kurze Begründung für diese spezifische Stunde (z.B. 'Wind 15 km/h aus optimaler Richtung, gute Thermik erwartet')"
    },
    {
      "hour": 10,
      "timestamp": "2026-01-04T10:00:00Z",
      "conditions": "EXCELLENT/GOOD/MODERATE/POOR/DANGEROUS",
      "flyable": true/false,
      "rating": 1-10,
      "reason": "Kurze Begründung"
    }
    // ... für jede Stunde im Flugstunden-Zeitraum
  ]
}"""

# User-Prompt Template (mit Platzhaltern für dynamische Werte)
# Platzhalter: {name}, {fluggebiet}, {typ}, {windrichtung}, {besonderheiten}, 
#              {hourly_data}, {wind_check_info}, {total_hours}, {flight_hours_start}, {flight_hours_end}
LLM_USER_PROMPT_TEMPLATE = """Analysiere die Flugbarkeit für folgenden Startplatz:

STARTPLATZ-INFO:
Name: {name}
Region: {fluggebiet}
Typ: {typ}
Erlaubte Windrichtungen: {windrichtung}

WICHTIG - WINDRICHTUNGS-INTERPRETATION:
- Einzelne Richtungen sind Punkte: N=0°/360°, NO=45°, O=90°, SO=135°, S=180°, SW=225°, W=270°, NW=315°
- "{windrichtung}" ist eine RANGE (nicht eine einzelne Richtung!)
- Beispiel "N-O": Dies bedeutet eine RANGE von Nord (0°/360°) bis Ost (90°)
  * WICHTIG: Die Range geht NICHT über 360° hinaus!
  * "N-O" bedeutet EXAKT: 0° bis 90° (nicht 337.5° bis 112.5°!)
  * Windrichtungen zwischen 0° und 90° liegen INNERHALB dieser erlaubten Range!
  * Windrichtungen außerhalb von 0°-90° liegen AUSSERHALB dieser Range!
- Weitere Beispiele:
  * "NO-SO" = 45° bis 135°
  * "W-NW" = 270° bis 315°
  * "N-NO" = 0° bis 45°
Besonderheiten: {besonderheiten}

AKTUELLE WETTERDATEN (erste 6 Stunden):
{hourly_data}

WETTERENTWICKLUNG:
Es stehen {total_hours} Stunden Forecast-Daten zur Verfügung. Fokussiere auf die nächsten 3-6 Stunden für die Flugbarkeits-Entscheidung.

WICHTIG: STÜNDLICHE BEWERTUNGEN ERFORDERLICH:
- Du MUSST für JEDE einzelne Stunde im Flugstunden-Zeitraum ({flight_hours_start}:00-{flight_hours_end}:00) eine separate Bewertung abgeben
- Bewerte jede Stunde einzeln basierend auf den Wetterdaten dieser spezifischen Stunde
- Für jede Stunde gib an: conditions (EXCELLENT/GOOD/MODERATE/POOR/DANGEROUS), flyable (true/false), rating (1-10), reason (kurze Begründung)
- Zusätzlich gibst du ein Gesamt-Fazit für den ganzen Tag (summary, details, recommendation)

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

# ============================================================================
# REGIONEN-KONFIGURATION (29 Thermikregionen)
# IDs, lat/lon und elevation_ref stammen aus regionen_referenzpunkte.geojson
# (= echte Gleitschirm-Startplätze als Referenzpunkte pro Region)
# Jede Region hat genau ein Polygon in regionen_xc_thermik.geojson
# ============================================================================

REGIONS = [
    # --- Jura ---
    {"id": "jura_west", "name": "Jura West", "lat": 46.8286, "lon": 6.5401, "elevation_ref": 1200},
    {"id": "jura_zentral", "name": "Jura Zentral", "lat": 47.2536, "lon": 7.5097, "elevation_ref": 1280},
    {"id": "jura_ost", "name": "Jura Ost", "lat": 47.42, "lon": 7.957, "elevation_ref": 900},
    # --- Mittelland ---
    {"id": "mittelland_west", "name": "Mittelland West", "lat": 46.6685, "lon": 6.7972, "elevation_ref": 700},
    {"id": "seeland_emmental", "name": "Seeland / Emmental", "lat": 47.14, "lon": 7.60, "elevation_ref": 600},
    {"id": "mittelland_zentral", "name": "Mittelland Zentral", "lat": 47.0041, "lon": 7.9395, "elevation_ref": 1400},
    {"id": "mittelland_ost", "name": "Mittelland Ost", "lat": 47.3504, "lon": 8.4907, "elevation_ref": 730},
    # --- Voralpen ---
    {"id": "genferseeregion", "name": "Genferseeregion", "lat": 46.38, "lon": 6.38, "elevation_ref": 800},
    {"id": "freiburger_voralpen", "name": "Freiburger Voralpen", "lat": 46.5492, "lon": 7.0175, "elevation_ref": 1950},
    {"id": "schwarzsee_gantrisch", "name": "Schwarzsee / Gantrisch", "lat": 46.65, "lon": 7.10, "elevation_ref": 1500},
    {"id": "berner_oberland", "name": "Berner Oberland", "lat": 46.85, "lon": 7.75, "elevation_ref": 1800},
    {"id": "berner_voralpen", "name": "Berner Voralpen", "lat": 46.7082, "lon": 7.7731, "elevation_ref": 1950},
    {"id": "zentralschweizer_voralpen", "name": "Zentralschweizer Voralpen", "lat": 46.837, "lon": 8.406, "elevation_ref": 1860},
    {"id": "glarnerland_walensee", "name": "Glarnerland / Walensee", "lat": 47.135, "lon": 9.294, "elevation_ref": 1300},
    {"id": "alpstein", "name": "Alpstein / Ostschweiz", "lat": 47.2839, "lon": 9.4081, "elevation_ref": 1640},
    # --- Wallis ---
    {"id": "unterwallis", "name": "Unterwallis", "lat": 46.0844, "lon": 7.2458, "elevation_ref": 2200},
    {"id": "mattertal_saastal", "name": "Mattertal / Saastal", "lat": 46.06, "lon": 7.65, "elevation_ref": 2000},
    {"id": "waadtlaender_alpen", "name": "Waadtländer Alpen", "lat": 46.26, "lon": 7.00, "elevation_ref": 1600},
    {"id": "zentralwallis", "name": "Zentralwallis", "lat": 46.47, "lon": 7.85, "elevation_ref": 2100},
    {"id": "oberwallis_goms", "name": "Oberwallis / Goms", "lat": 46.4086, "lon": 8.1102, "elevation_ref": 2200},
    # --- Alpen Zentral ---
    {"id": "haslital_grimsel", "name": "Haslital / Grimselgebiet", "lat": 46.745, "lon": 8.243, "elevation_ref": 2200},
    {"id": "urner_alpen", "name": "Urner Alpen", "lat": 46.901, "lon": 8.647, "elevation_ref": 1500},
    {"id": "surselva", "name": "Surselva", "lat": 46.8353, "lon": 9.2131, "elevation_ref": 2200},
    # --- Ostschweiz / Graubuenden ---
    {"id": "chur_mittelbuenden", "name": "Chur / Mittelbünden", "lat": 46.993, "lon": 9.68, "elevation_ref": 1700},
    {"id": "engadin_ober", "name": "Engadin Ober", "lat": 46.5225, "lon": 9.9028, "elevation_ref": 2450},
    {"id": "engadin_unter", "name": "Engadin Unter", "lat": 46.8125, "lon": 10.2786, "elevation_ref": 2100},
    # --- Tessin / Suedbuenden ---
    {"id": "tessin_nord", "name": "Tessin Nord", "lat": 46.4861, "lon": 8.815, "elevation_ref": 2000},
    {"id": "tessin_zentral", "name": "Tessin Zentral", "lat": 46.2025, "lon": 8.7944, "elevation_ref": 1650},
    {"id": "suedbuenden", "name": "Südbünden", "lat": 46.2644, "lon": 9.145, "elevation_ref": 1500},
]
