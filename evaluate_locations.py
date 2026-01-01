#!/usr/bin/env python3
"""
Skript zur Evaluierung der besten Gleitschirmflug-Standorte basierend auf Wetterdaten.
Das LLM führt die Bewertung selbstständig durch basierend auf den übergebenen Kriterien.
"""

import json
import os
from datetime import datetime
from re import L
import config

# Lade Umgebungsvariablen aus .env Datei
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # python-dotenv nicht installiert, verwende System-Umgebungsvariablen
    pass

# Bewertungskriterien für das LLM
# Diese können einfach erweitert oder angepasst werden
EVALUATION_CRITERIA = {
    "cloud_cover": {
        "priority": 1,  # Höchste Priorität - wird zuerst bewertet
        "description": "Bewölkungsgrad muss möglichst gering sein. Je niedriger, desto besser.",
        "evaluation_notes": "0% ist optimal, 100% ist schlecht"
    },
    "wind_speed": {
        "priority": 2,
        "description": "Windgeschwindigkeit: Optimal ist 10-20 km/h. Gut ist 0-10 km/h. Kritisch wird es bei 20-30 km/h. Ab 30 km/h ist es nicht mehr fliegbar.",
        "evaluation_notes": "Windstärke ist kritisch für die Sicherheit"
    }
}

# Konfigurierbare Zeitfenster für Gleitschirmfliegen
DAYTIME_HOURS = (9, 17)  # Von 9 bis 17 Uhr

# OpenAI Modell-Konfiguration
OPENAI_MODEL = "gpt-4o-mini"


def load_weather_data(json_path):
    """
    Lädt Wetterdaten aus der JSON-Datei.
    
    Args:
        json_path: Pfad zur JSON-Datei
        
    Returns:
        Dictionary mit Wetterdaten oder None bei Fehler
    """
    try:
        if not os.path.exists(json_path):
            print(f"[FEHLER] Datei nicht gefunden: {json_path}")
            return None
        
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"[INFO] Wetterdaten geladen: {len(data)} Standorte gefunden")
        return data
        
    except Exception as e:
        print(f"[FEHLER] Fehler beim Laden der Daten: {e}")
        return None


def filter_daytime_hours(hourly_data, start_hour, end_hour):
    """
    Filtert Stunden zwischen start_hour und end_hour aus den stündlichen Daten.
    
    Args:
        hourly_data: Dictionary mit Zeitstempeln als Keys und Wetterdaten als Values
        start_hour: Startstunde (z.B. 9)
        end_hour: Endstunde (z.B. 17)
        
    Returns:
        Dictionary mit gefilterten Stunden
    """
    filtered = {}
    
    for time_str, weather_values in hourly_data.items():
        try:
            # Parse Zeitstempel (Format: "2026-01-01T09:00")
            dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
            hour = dt.hour
            
            # Filtere Stunden zwischen start_hour und end_hour
            if start_hour <= hour <= end_hour:
                filtered[time_str] = weather_values
                
        except Exception as e:
            print(f"[WARNUNG] Fehler beim Parsen von {time_str}: {e}")
            continue
    
    return filtered


def convert_wind_speed_to_kmh(wind_speed_ms):
    """
    Konvertiert Windgeschwindigkeit von m/s zu km/h.
    
    Args:
        wind_speed_ms: Windgeschwindigkeit in m/s
        
    Returns:
        Windgeschwindigkeit in km/h
    """
    if wind_speed_ms is None:
        return None
    return wind_speed_ms * 3.6


def prepare_location_data(location_name, location_data):
    """
    Bereitet Daten eines Standorts für das LLM auf.
    
    Args:
        location_name: Name des Standorts
        location_data: Dictionary mit Standortdaten (latitude, longitude, hourly_data)
        
    Returns:
        Dictionary mit aufbereiteten Standortdaten
    """
    hourly_data = location_data.get("hourly_data", {})
    
    # Filtere Stunden zwischen 9-17 Uhr
    daytime_data = filter_daytime_hours(hourly_data, DAYTIME_HOURS[0], DAYTIME_HOURS[1])
    
    # Bereite Stunden-Daten auf
    prepared_hours = []
    
    for time_str, weather_values in sorted(daytime_data.items()):
        try:
            dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
            time_display = dt.strftime("%Y-%m-%d %H:%M")
            
            # Konvertiere Windgeschwindigkeit zu km/h (falls in m/s)
            wind_speed = weather_values.get("wind_speed_10m")
            wind_speed_kmh = convert_wind_speed_to_kmh(wind_speed) if wind_speed is not None else None
            
            hour_data = {
                "zeit": time_display,
                "bewölkungsgrad": weather_values.get("cloud_cover"),
                "windgeschwindigkeit_kmh": wind_speed_kmh,
                "windrichtung": weather_values.get("wind_direction_10m"),
                "bewölkungshöhe_m": weather_values.get("cloud_base"),
                "temperatur_c": weather_values.get("temperature_2m")
            }
            
            prepared_hours.append(hour_data)
            
        except Exception as e:
            print(f"[WARNUNG] Fehler beim Aufbereiten von {time_str}: {e}")
            continue
    
    return {
        "standort": location_name,
        "koordinaten": {
            "latitude": location_data.get("latitude"),
            "longitude": location_data.get("longitude")
        },
        "stunden": prepared_hours,
        "anzahl_stunden": len(prepared_hours)
    }


def prepare_all_locations_data(weather_data):
    """
    Bereitet alle Standorte für das LLM auf.
    
    Args:
        weather_data: Dictionary mit allen Standortdaten
        
    Returns:
        Liste von aufbereiteten Standortdaten
    """
    locations_list = []
    
    for location_name, location_data in weather_data.items():
        prepared = prepare_location_data(location_name, location_data)
        locations_list.append(prepared)
        print(f"[INFO] Standort aufbereitet: {location_name} ({prepared['anzahl_stunden']} Stunden)")
    
    return locations_list


def build_evaluation_prompt(locations_data, criteria):
    """
    Erstellt den Prompt für das LLM mit Daten und Bewertungskriterien.
    
    Args:
        locations_data: Liste von aufbereiteten Standortdaten
        criteria: Dictionary mit Bewertungskriterien
        
    Returns:
        Vollständiger Prompt als String
    """
    # Sortiere Kriterien nach Priorität
    sorted_criteria = sorted(criteria.items(), key=lambda x: x[1]["priority"])
    
    # Baue Kriterien-Text
    criteria_text = "BEWERTUNGSKRITERIEN (in Prioritätsreihenfolge):\n"
    for i, (key, value) in enumerate(sorted_criteria, 1):
        criteria_text += f"{i}. {value['description']}\n"
        if value.get("evaluation_notes"):
            criteria_text += f"   Hinweis: {value['evaluation_notes']}\n"
        criteria_text += "\n"
    
    # Baue Wetterdaten-Text
    weather_text = "WETTERDATEN DER STANDORTE:\n\n"
    for location in locations_data:
        weather_text += f"Standort: {location['standort']}\n"
        weather_text += f"Koordinaten: {location['koordinaten']['latitude']}, {location['koordinaten']['longitude']}\n"
        weather_text += f"Anzahl Stunden (9-17 Uhr): {location['anzahl_stunden']}\n\n"
        
        weather_text += "Stündliche Wetterdaten:\n"
        for hour in location['stunden']:
            weather_text += f"  {hour['zeit']}:\n"
            weather_text += f"    - Bewölkungsgrad: {hour['bewölkungsgrad']}%\n"
            if hour['windgeschwindigkeit_kmh'] is not None:
                weather_text += f"    - Windgeschwindigkeit: {hour['windgeschwindigkeit_kmh']:.1f} km/h\n"
            else:
                weather_text += f"    - Windgeschwindigkeit: N/A\n"
            weather_text += f"    - Windrichtung: {hour['windrichtung']}°\n"
            weather_text += f"    - Bewölkungshöhe: {hour['bewölkungshöhe_m']} m\n"
            weather_text += f"    - Temperatur: {hour['temperatur_c']}°C\n"
        weather_text += "\n" + "="*60 + "\n\n"
    
    # Vollständiger Prompt
    prompt = f"""Du bist ein Experte für Gleitschirmfliegen und Wetteranalyse. Deine Aufgabe ist es, die folgenden Standorte basierend auf ihren Wetterbedingungen für Gleitschirmfliegen zu bewerten.

{criteria_text}

BEWERTUNGSANWEISUNGEN:
1. Bewerte jede Stunde zwischen 9-17 Uhr einzeln und vergebe einen Score von 0-10 pro Stunde
   - 10 = Perfekt für Gleitschirmfliegen
   - 7-9 = Sehr gut
   - 4-6 = Akzeptabel
   - 1-3 = Schlecht
   - 0 = Nicht fliegbar

2. Berechne einen Gesamtscore pro Standort (Durchschnitt aller Stunden-Scores)

3. Erstelle eine Rangliste aller Standorte (bester zuerst)

4. Gib für jeden Standort an:
   - Gesamtscore (0-10)
   - Anzahl "gute Stunden" (Score >= 7)
   - Beste Zeitfenster für Flüge
   - Wichtigste positive und negative Aspekte
   - Kurze Begründung der Bewertung

5. Formatiere die Antwort übersichtlich mit klaren Abschnitten für jeden Standort

{weather_text}

Bitte führe nun die Bewertung durch und erstelle die Rangliste."""
    
    return prompt


def call_openai_api(prompt):
    """
    Ruft die OpenAI API auf.
    
    Args:
        prompt: Der Prompt für das LLM
        
    Returns:
        Antwort des LLMs oder None bei Fehler
    """
    try:
        import openai
        
        # Prüfe ob API-Key gesetzt ist
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OPENAI_API_KEY Umgebungsvariable nicht gesetzt! Bitte setzen Sie die Variable mit Ihrem OpenAI API-Key.")
        
        client = openai.OpenAI(api_key=api_key)
        
        print("[INFO] Rufe OpenAI API auf...")
        
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "Du bist ein Experte für Gleitschirmfliegen und Wetteranalyse. Du bewertest Wetterbedingungen für Gleitschirmfliegen präzise und detailliert."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.7,
            max_tokens=4000
        )
        
        return response.choices[0].message.content
        
    except ImportError:
        print("[FEHLER] openai-Paket nicht installiert.")
        print("[INFO] Installiere es mit: pip install openai")
        return None
    except Exception as e:
        print(f"[FEHLER] Fehler beim Aufruf der OpenAI API: {e}")
        return None


def main():
    """
    Hauptfunktion: Lädt Wetterdaten und evaluiert Standorte mit LLM.
    """
    print(f"\n{'='*60}")
    print("GLEITSCHIRMFLUG-STANDORT EVALUIERUNG")
    print(f"{'='*60}\n")
    
    # Lade Wetterdaten
    json_path = os.path.join(config.OUTPUT_DIR, "wetterdaten.json")
    weather_data = load_weather_data(json_path)
    
    if not weather_data:
        print("[FEHLER] Keine Wetterdaten gefunden. Bitte führen Sie zuerst fetch_weather.py aus.")
        return
    
    # Bereite Daten auf
    print(f"\n{'='*60}")
    print("BEREITE DATEN AUF")
    print(f"{'='*60}\n")
    
    locations_data = prepare_all_locations_data(weather_data)
    
    if not locations_data:
        print("[FEHLER] Keine Standorte zum Evaluieren gefunden.")
        return
    
    # Erstelle Prompt
    print(f"\n{'='*60}")
    print("ERSTELLE EVALUIERUNGSPROMPT")
    print(f"{'='*60}\n")
    
    prompt = build_evaluation_prompt(locations_data, EVALUATION_CRITERIA)
    
    # Rufe LLM auf
    print(f"\n{'='*60}")
    print("EVALUIERUNG DURCH LLM")
    print(f"{'='*60}\n")
    
    evaluation = call_openai_api(prompt)
    
    if not evaluation:
        print("[FEHLER] Evaluierung fehlgeschlagen.")
        return
    
    # Zeige Ergebnis
    print("\n" + "="*60)
    print("EVALUIERUNGSERGEBNIS")
    print("="*60)
    print(evaluation)
    print("="*60 + "\n")


if __name__ == "__main__":
    main()

