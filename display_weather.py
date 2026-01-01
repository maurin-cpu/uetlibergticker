#!/usr/bin/env python3
"""Skript zur Anzeige der Wetterdaten aus der JSON-Datei"""

import json
import os
from datetime import datetime
import config

# Pfad zur JSON-Datei mit Wetterdaten
JSON_FILE_PATH = os.path.join(config.OUTPUT_DIR, "wetterdaten.json")


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
            print(f"[FEHLER] JSON-Datei nicht gefunden: {json_path}")
            return None
        
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return data
        
    except Exception as e:
        print(f"[FEHLER] Fehler beim Lesen der JSON-Datei: {e}")
        return None


def display_weather_for_location(location_name, weather_data):
    """
    Zeigt Wetterdaten für einen Standort an.
    
    Args:
        location_name: Name des Standorts
        weather_data: Dictionary mit Wetterdaten für den Standort
    """
    if not weather_data:
        print(f"[WARNUNG] Keine Daten für {location_name}")
        return
    
    latitude = weather_data.get('latitude')
    longitude = weather_data.get('longitude')
    hourly_data = weather_data.get('hourly_data', {})
    
    if not hourly_data:
        print(f"[WARNUNG] Keine stündlichen Daten für {location_name}")
        return
    
    print(f"\n{'='*60}")
    print(f"WETTERVORHERSAGE - NÄCHSTE 5 TAGE")
    print(f"MeteoSwiss ICON-CH Modell (CH1)")
    print(f"Standort: {location_name} ({latitude}, {longitude})")
    print(f"{'='*60}\n")
    
    # Gruppiere nach Tagen für bessere Übersicht
    days_data = {}
    for time_str, values in hourly_data.items():
        dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
        date_key = dt.strftime("%Y-%m-%d")
        if date_key not in days_data:
            days_data[date_key] = []
        days_data[date_key].append((time_str, values))
    
    # Zeige alle Zeitstempel, gruppiert nach Tagen
    for date_key in sorted(days_data.keys()):
        day_timestamps = sorted(days_data[date_key], key=lambda x: x[0])  # Sortiere nach Zeitstempel
        dt_first = datetime.fromisoformat(day_timestamps[0][0].replace("Z", "+00:00"))
        date_display = dt_first.strftime("%d.%m.%Y")
        
        print(f"\n{'='*80}")
        print(f"Tag: {date_display}")
        print(f"{'='*80}")
        
        # Zeige jeden Zeitstempel des Tages
        for time_str, values in day_timestamps:
            dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
            time_display = dt.strftime("%H:%M")
            
            print(f"\nZeitstempel: {time_display}")
            print("-" * 80)
            
            # Formatierung der Werte
            temp = values.get("temperature_2m")
            cb = values.get("cloud_base")
            cc = values.get("cloud_cover")
            ws = values.get("wind_speed_10m")
            wd = values.get("wind_direction_10m")
            prec = values.get("precipitation")
            prec_prob = values.get("precipitation_probability")
            cc_low = values.get("cloud_cover_low")
            cc_mid = values.get("cloud_cover_mid")
            cc_high = values.get("cloud_cover_high")
            sunshine = values.get("sunshine_duration")
            
            print(f"Temperatur:              {temp:.1f}°C" if temp is not None else "Temperatur:              N/A")
            print(f"Bewölkungshöhe:          {cb:.0f}m" if cb is not None else "Bewölkungshöhe:          N/A")
            print(f"Bewölkungsgrad (gesamt): {cc:.0f}%" if cc is not None else "Bewölkungsgrad (gesamt): N/A")
            print(f"Bewölkung tief:          {cc_low:.0f}%" if cc_low is not None else "Bewölkung tief:          N/A")
            print(f"Bewölkung mittel:        {cc_mid:.0f}%" if cc_mid is not None else "Bewölkung mittel:        N/A")
            print(f"Bewölkung hoch:          {cc_high:.0f}%" if cc_high is not None else "Bewölkung hoch:          N/A")
            print(f"Niederschlag:            {prec:.2f}mm" if prec is not None else "Niederschlag:            N/A")
            print(f"Niederschlagswahrscheinlichkeit: {prec_prob:.0f}%" if prec_prob is not None else "Niederschlagswahrscheinlichkeit: N/A")
            if sunshine is not None:
                sunshine_hours = sunshine / 3600
                print(f"Sonnenscheindauer:       {sunshine_hours:.2f}h ({sunshine:.0f}s)")
            else:
                print(f"Sonnenscheindauer:       N/A")
            if ws is not None:
                ws_kmh = ws * 3.6
                print(f"Windgeschwindigkeit:     {ws_kmh:.1f}km/h ({ws:.1f}m/s)")
            else:
                print(f"Windgeschwindigkeit:     N/A")
            print(f"Windrichtung:            {wd:.0f}°" if wd is not None else "Windrichtung:            N/A")
    
    print(f"\n{'='*80}")
    print(f"[INFO] Gesamt {len(hourly_data)} Zeitstempel angezeigt")


def display_all_locations():
    """
    Zeigt Wetterdaten für alle Standorte aus der JSON-Datei an.
    """
    weather_data = load_weather_data(JSON_FILE_PATH)
    
    if not weather_data:
        print("[FEHLER] Keine Wetterdaten gefunden.")
        return
    
    print(f"\n{'='*60}")
    print(f"WETTERVORHERSAGE FÜR {len(weather_data)} STANDORTE")
    print(f"{'='*60}\n")
    
    for location_name, location_data in weather_data.items():
        display_weather_for_location(location_name, location_data)
        print("\n")


def display_single_location(location_name):
    """
    Zeigt Wetterdaten für einen einzelnen Standort an.
    
    Args:
        location_name: Name des Standorts
    """
    weather_data = load_weather_data(JSON_FILE_PATH)
    
    if not weather_data:
        print("[FEHLER] Keine Wetterdaten gefunden.")
        return
    
    if location_name not in weather_data:
        print(f"[FEHLER] Standort '{location_name}' nicht gefunden.")
        print(f"Verfügbare Standorte: {', '.join(weather_data.keys())}")
        return
    
    display_weather_for_location(location_name, weather_data[location_name])


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        # Zeige nur einen Standort
        location_name = sys.argv[1]
        display_single_location(location_name)
    else:
        # Zeige alle Standorte
        display_all_locations()

