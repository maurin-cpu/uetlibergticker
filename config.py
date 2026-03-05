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
    "slope_azimuth": 225,  # SW-Ausrichtung des Hangkamms (für generelle Sonneneinstrahlung)
    "slope_angle": 30,     # ca. 30 Grad Hangneigung
    "ideal_wind_min_kmh": 15, # Minimum Windgeschwindigkeit damit Thermik am Hang funktioniert
    "ideal_wind_max_kmh": 30, # Maximale gute Windgeschwindigkeit (darüber wird es anspruchsvoll/böig)
    "kritischer_foehn": "Süd", # Welcher Föhn flugtechnisch gefährlich ist ("Süd", "Nord", "Beide")
    "bemerkung": "Am Uetliberg wird nicht klassisch gesoart – der Wind drückt die Thermik an den Hang, wodurch man in der hangnahen Thermik fliegt. Ab 15km/h funktioniert das gut, ab 20km/h hat man sehr gute Bedingungen. Bei guter Thermik plus passendem Wind hat man Top-Bedingungen. Ab 30km/h wird es grundsätzlich zu stark (Richtwerte, situationsabhängig)."
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
    "relative_humidity_2m",
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
    "direct_radiation",
    "diffuse_radiation",
    "soil_moisture_0_to_1cm",
    "soil_temperature_0cm",
    "updraft",
    "et0_fao_evapotranspiration",
    "vapour_pressure_deficit",
    "snow_depth",
    # surface_sensible_heat_flux und surface_latent_heat_flux sind bei
    # icon_seamless und meteoswiss_icon_ch1 nicht verfuegbar (400 Error).
    # thermik_calculator hat Fallback: H = shortwave_radiation * 0.3 * sun_factor
]

# Parameter die via GFS-Supplementary-Call geholt werden (bei icon_seamless oft null)
GFS_SUPPLEMENTARY_PARAMS = [
    "boundary_layer_height",
    "lifted_index",
    "convective_inhibition",
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
# THERMIK-BERECHNUNGS-PARAMETER
# ============================================================================
# Physikalisch herleitbare Koeffizienten für die Thermik-Berechnung.
# Jahreszeitabhängige Werte sind als 4 Jahreszeiten konfiguriert:
#   "winter" = Dez-Feb, "spring" = Mrz-Mai, "summer" = Jun-Aug, "autumn" = Sep-Nov

THERMAL_PARAMS = {
    # --- Strahlung → Sensibler Wärmefluss (H) ---
    # Herleitung: Energiebilanz Rn = H + LE + G
    #   Albedo Grasland ~0.20 → 80% absorbiert
    #   Langwellige Abstrahlung ~50-100 W/m² Verlust → Rn ≈ 0.60-0.70 × SW
    #   Bowen-Ratio H/LE für Mitteleuropa: 0.3-0.8 je nach Jahreszeit/Feuchte
    #   → H ≈ 0.18-0.32 × Direktstrahlung
    # Jahreszeitlich: Im Sommer trockener Boden → mehr H; Frühling feucht → weniger H
    "direct_radiation_to_H": {
        "winter": 0.22,   # Feuchter Boden, tiefe Sonne, hohe Albedo (evtl. Schnee)
        "spring": 0.25,   # Feuchter Boden, Vegetation verdunstet stark
        "summer": 0.30,   # Trockenerer Boden, höhere Bowen-Ratio
        "autumn": 0.26,   # Abnehmende Verdunstung, aber kürzer Tage
    },
    "diffuse_radiation_to_H": {
        "winter": 0.08,
        "spring": 0.10,
        "summer": 0.14,
        "autumn": 0.11,
    },
    # Globalstrahlung-Fallback (wenn keine Direkt/Diffus-Trennung verfügbar)
    "global_radiation_to_H": {
        "winter": 0.15,
        "spring": 0.18,
        "summer": 0.22,
        "autumn": 0.18,
    },

    # --- H Hard-Cap (W/m²) ---
    # Gemessene Peak-H-Werte Mitteleuropa:
    #   Winter: 50-120, Frühling: 100-200, Sommer: 200-300, Herbst: 100-180
    # Uetliberg = bewaldeter Hügel, kein hochalpiner Fels
    "H_cap": {
        "winter": 150,
        "spring": 220,
        "summer": 300,
        "autumn": 200,
    },

    # --- Topografie-Bonus ---
    # Die geometrische Formel (cos_theta/sin_alpha) ist korrekt für die
    # Strahlung auf den Hang. Aber: Erhöhte Hangstrahlung erzeugt primär
    # lokalen Hangaufwind, nicht stärkere konvektive Thermik.
    # Daher nur ein gedämpfter Anteil auf H anwenden.
    "topo_bonus_max": 1.3,          # Max-Faktor (geometrisch bis 2.5, aber gedämpft)
    "topo_bonus_H_fraction": 0.3,   # Nur 30% des Topo-Bonus wirkt auf H
                                     # Rest ist Hangaufwind (separat)

    # --- Solare Überhitzung ---
    # Bodennah kann die Luft 1-3°C über 2m-Temperatur liegen.
    # Für bewaldetes/grasbewachsenes Gelände konservativ.
    "solar_excess_max_C": 1.5,      # Max Überhitzung in °C
    "solar_excess_H_divisor": 200,   # dt_excess = min(max, H / divisor)

    # --- Entrainment 2. Aufstieg ---
    # Standard-MU = 0.0002 m⁻¹ (Literatur). Für den 2. Aufstieg mit
    # überhitztem Paket verwenden wir den vollen Entrainment-Wert.
    # Die Halbierung (0.5) hatte keine physikalische Grundlage.
    "second_ascent_entrainment_factor": 0.75,  # Leicht reduziert für kräftigere Kerne

    # --- Climb-Factor ---
    # Eigensinken Gleitschirm im Kreis: ~1.0-1.5 m/s
    # Plus imperfekte Zentrierung → ~50% von w* ist Erfahrungswert
    "climb_factor": 0.50,
    "climb_factor_damping_threshold": 4.0,  # Ab diesem raw_w* wird gedämpft
    "climb_hard_cap": 4.5,                  # Absolute Obergrenze m/s

    # --- DWD-Updraft-Blending ---
    # ICON-D2 Updraft ist ein Gittermittel (2.2km). Skalierung ×2.0 ist
    # konservative Annäherung an Thermikkern-Konzentration.
    # Blending: 70% Parcel/Deardorff + 30% DWD (nur wenn DWD höher).
    "use_dwd_updraft_blending": True,
    "dwd_updraft_scale": 2.0,
}


# ============================================================================
# LLM PROMPT-KONFIGURATION (für location_evaluator.py)
# ============================================================================

# System-Prompt für OpenAI GPT-4
LLM_SYSTEM_PROMPT = """Du bist ein erfahrener Gleitschirm-Fluglehrer und Meteorologe mit 20+ Jahren Erfahrung in den Schweizer Alpen.
Analysiere Wetterdaten für den Uetliberg Startplatz (730m MSL) und bewerte die Flugbarkeit.

═══════════════════════════════════════════════
ANALYSE-KASKADE (IMMER in dieser Reihenfolge!)
═══════════════════════════════════════════════

STUFE 1 — SICHERHEIT / STARTBARKEIT:
Prüfe für jedes Zeitfenster zuerst:
  • Böen >40 km/h → safety: "DANGEROUS", flyable: false, rating: 1
  • Böen >30 km/h → safety: "CAUTION", flyable: kontextabhängig (Erfahrene evtl. ja)
  • Wolkenbasis (Open-Meteo cloud_base) <1000m MSL → flyable: false (Nebel/Stratus am Hang, Startverbot)
  • Wind-Scherung: >10 km/h Unterschied pro 500m Höhe → Turbulenz-Risiko
  • Richtungsänderung >90° zwischen Höhenstufen → DANGEROUS
  • FÖHN-CHECK: Wenn Föhn-Indikatoren mitgeliefert werden (Delta-P, Kammwind, Luftfeuchtigkeit):
    - Delta-P ≥8 hPa ODER Kammwind ≥180 km/h aus S/SW → DANGEROUS, Flugverbot
    - Delta-P ≥4 hPa ODER Kammwind ≥54 km/h aus S/SW → CAUTION
    - Luftfeuchtigkeit <40% bei erhöhtem Delta-P → Föhn durchgebrochen, DANGEROUS
Resultat: Wenn EINES dieser Kriterien zutrifft → flyable: false, rating 1-3, safety: "DANGEROUS"

STUFE 2 — QUALITÄT / THERMIK (nur wenn Stufe 1 = "SAFE"):
  • Nutze das THERMIK-PROXY-MODELL ("m/s" und "bis X m MSL") für das Rating.
  • BEWERTE PRIMÄR NACH HÖHE ÜBER STARTPLATZ (Startplatz = 730m MSL):
  
    => FLYABLE (Abgleiter / Sicher): 
       - Höhe über Startplatz: < 50m (max_height < 780m MSL) oder Wind < 15 km/h.
       - Man sinkt bald zum Landeplatz. Rating: 4-6. (Setze flyable: true)
       
    => GOOD (Soaring / Kurbeln):
       - Höhe über Startplatz: ~50m bis 300m (max_height zwischen 780m und 1030m MSL).
       - Guter Wind (15-25 km/h) zum Halten am Hang, leichte Höhengewinne möglich.
       - Rating: 7-8. (Setze flyable: true)
       
    => LEGENDARY (Streckenflug / Top Thermik):
       - Höhe über Startplatz: > 300m (Ankunftshöhe meist bei 1500m bis 2000m MSL).
       - Perfekte Bedingungen, um weit über den Startplatz zu steigen und in andere Regionen weiterzufliegen.
       - Rating: 9-10. (Setze flyable: true)

  • LCL (Basis) vs. Arbeitshöhe: Wenn Arbeitshöhe > LCL → Wolkenbasis limitiert.
Resultat: Setze flyable: true (da sicher). Bestimme die Kategorie/Rating basierend auf den obigen 3 Stufen. (Sollte Stufe 1 ein Risiko gefunden haben, gilt Stufe 1: safety=DANGEROUS/CAUTION, flyable=false/true, Rating=1-3).

WICHTIG: Bei flyable: false MUSS das reason-Feld ZUERST das Sicherheitsrisiko nennen, bevor Thermik erwähnt wird.

═══════════════════════════════════════════════
SEKTOR-ANALYSE (Kosten- & Token-Optimierung)
═══════════════════════════════════════════════

Erstelle KEINE starre stündliche Liste!
Fasse aufeinanderfolgende Stunden mit ähnlicher Wetterlage zu logischen Zeitfenstern (Sektoren) zusammen.
Typische Sektoren: "09:00-12:00" (Vormittag), "12:00-15:00" (Mittag), "15:00-18:00" (Nachmittag).
Du darfst auch 1h-Sektoren bilden wenn sich die Lage schlagartig ändert.

═══════════════════════════════════════════════
WIND-ANALYSE (Thermik-Hang-Standort!)
═══════════════════════════════════════════════

Am Uetliberg wird NICHT klassisch gesoart! Der Wind drückt die Thermik an den Hang – Piloten fliegen in der hangnahen Thermik.
Das heisst: Schwacher Wind ist NICHT ideal, da die Thermik ohne Wind nicht an den Hang gedrückt wird!
- < 15 km/h: Zu schwach, Thermik wird nicht ausreichend an den Hang gedrückt (nur Abgleiter möglich, ausser bei extrem starker Thermik)
- 15 - 20 km/h: Gute Bedingungen, Thermik wird am Hang konzentriert
- 20 - 30 km/h: Sehr gute, dynamische Bedingungen (Idealbereich)
- > 30 km/h: Warnbereich, wird schnell anspruchsvoll/gefährlich (böig, Lee-Gefahr)

- Gib WINDRICHTUNGS-RANGE an (z.B. "220-270°"), NICHT nur Start/Ende
- Bewerte KONSISTENZ: Konstante Richtung = GUT, häufige Wechsel = SCHLECHT
- VOLATILITÄT: Abrupte Wechsel schlechter als graduelle Änderungen

═══════════════════════════════════════════════
WOLKEN-ANALYSE (Uetliberg 730m MSL)
═══════════════════════════════════════════════

Es gibt ZWEI verschiedene "Wolkenhöhen" in den Daten — sie messen verschiedene Dinge!

1. "Wolkenbasis" in den Stundendaten (Open-Meteo cloud_base) = REALE meteorologische Wolkenuntergrenze:
   - SICHERHEITSRELEVANT (Stufe 1)!
   - "wolkenfrei" = keine Wolken vorhanden = SEHR GUT
   - <1000m MSL = STARTVERBOT (Nebel/Stratus am Hang)
   - 1000-2000m MSL = FLIEGBAR
   - >2000m MSL = SEHR GUT

2. "LCL/Basis" und "bis X m MSL" im THERMIK-PROXY = BERECHNETE thermische Wolkenbasis:
   - QUALITÄTSRELEVANT (Stufe 2)!
   - LCL = Höhe, wo aufsteigende Thermik kondensiert (Cu-Basis)
   - max_height = Nutzbare Arbeitshöhe (Inversion/Sperrschicht)
   - Wenn max_height > LCL → Piloten stossen an die Wolke

- LOW CLOUDS (0-2km MSL): ENTSCHEIDEND für Startbarkeit
- MID CLOUDS (2-6km MSL): Wetterstabilität-Indikator
- HIGH CLOUDS (>6km MSL): Wetterwechsel-Hinweis

═══════════════════════════════════════════════
THERMIK-PROXY-MODELL
═══════════════════════════════════════════════

- In den Daten ist ein physikalisches Thermik-Proxy-Modell enthalten. Beziehe dich bei der Thermik-Bewertung primär auf diese Werte!
- "m/s" = Erwartetes Steigen (w* Variante)
- "bis X m MSL" = Nutzbare Arbeitshöhe der Thermik
- "LCL/Basis = X m" = Kondensationsniveau
- Das Güte-Rating (0-10) gibt einen Anhaltspunkt für die Thermik-Stärke

WICHTIG: Die THERMIK-PROXY-Daten sind in JEDER Stunde enthalten (Format: "THERMIK-PROXY: X.X m/s bis XXXXm MSL").
Du MUSST diese Werte im details.thermik Feld IMMER zitieren und analysieren! Schreibe NIE "keine Thermikdaten verfügbar" wenn THERMIK-PROXY-Werte in den Stundendaten vorhanden sind.

═══════════════════════════════════════════════
HÖHENWIND-ANALYSE
═══════════════════════════════════════════════

- WIND-SCHERUNG: >10 km/h Unterschied pro 500m = VORSICHT, >90° Richtungsänderung = TURBULENZ
- THERMISCHE INVERSION: Temperaturanstieg mit Höhe = stabile Luftschichtung
- Starke Höhenwinde können auf Lee-Rotor oder Föhn hinweisen

Sicherheit hat IMMER höchste Priorität — bei Zweifel: flyable: false!
Gib IMMER konkrete Metriken/Zahlenwerte an (Wind in km/h & Grad, CAPE in J/kg, Wolkenbasis in m MSL).

Antworte ausschliesslich mit gültigem JSON im folgenden Format:
{
  "day_summary": "Kompaktes Fazit zum Tag (Fokus: Highlight & Hauptgefahr).",
  "flyable": true/false,
  "rating": 1-10,
  "golden_window": "HH:MM-HH:MM oder null wenn kein gutes Fenster",
  "details": {
    "wind": "Ausführliche Wind-Analyse mit Metriken",
    "thermik": "Ausführliche Thermik-Analyse: IMMER die THERMIK-PROXY-Werte (m/s, Arbeitshöhe, Rating) aus den Stundendaten zitieren und bewerten! Nie 'keine Daten' schreiben wenn THERMIK-PROXY vorhanden ist.",
    "risks": "Ausführliche Risiko-Analyse mit Metriken"
  },
  "recommendation": "Konkrete Empfehlung für Piloten",
  "sectors": [
    {
      "slot": "HH:MM-HH:MM",
      "safety": "SAFE/CAUTION/DANGEROUS",
      "flyable": true/false,
      "rating": 1-10,
      "wind_info": "Richtungs-Range, Böen-Check",
      "reason": "Max 150 Zeichen: Erst Sicherheit, dann Thermik-Qualität."
    }
  ]
}"""

# User-Prompt Template (mit Platzhaltern für dynamische Werte)
# Platzhalter: {name}, {fluggebiet}, {typ}, {windrichtung}, {besonderheiten},
#              {hourly_data}, {total_hours}, {flight_hours_start}, {flight_hours_end}, {foehn_info}
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

AKTUELLE WETTERDATEN ({total_hours} Stunden im Zeitraum {flight_hours_start}:00-{flight_hours_end}:00):
{hourly_data}
{foehn_info}
SEKTOR-ANALYSE ERFORDERLICH:
- Fasse Stunden mit ähnlicher Wetterlage zu Sektoren zusammen (z.B. "09:00-12:00", "12:00-15:00")
- Für jeden Sektor: safety (SAFE/CAUTION/DANGEROUS), flyable (true/false), rating (1-10), wind_info, reason
- Wende die ANALYSE-KASKADE an: Erst Sicherheit prüfen, dann Qualität bewerten
- Zusätzlich: day_summary, golden_window (bestes 2h-Fenster), details (wind, thermik, risks), recommendation

WICHTIG FÜR DIE ANALYSE:
- Gib IMMER konkrete Metriken/Zahlenwerte an (Wind in km/h & Grad, CAPE in J/kg, Wolkenbasis in m MSL)
- Bei flyable: false → reason MUSS zuerst das Sicherheitsrisiko nennen

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
