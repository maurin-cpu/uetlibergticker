#!/usr/bin/env python3
"""Einfaches Skript zur Abfrage der Wettervorhersage von Swiss Meteo (konfigurierbar über config.py)"""

import requests
import math
import json
import os
import csv
from datetime import datetime
import config

def load_locations_from_csv(csv_path):
    """
    Liest Standorte aus einer CSV-Datei ein.
    
    Args:
        csv_path: Pfad zur CSV-Datei
        
    Returns:
        Liste von Dictionaries mit 'name', 'latitude', 'longitude'
    """
    locations = []
    
    try:
        if not os.path.exists(csv_path):
            print(f"[WARNUNG] CSV-Datei nicht gefunden: {csv_path}")
            return locations
        
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row_num, row in enumerate(reader, start=2):  # Start bei 2 wegen Header
                try:
                    name = row.get('Name', '').strip()
                    latitude_str = row.get('Latitude', '').strip()
                    longitude_str = row.get('Longitude', '').strip()
                    
                    # Überspringe leere Zeilen
                    if not name or not latitude_str or not longitude_str:
                        continue
                    
                    # Konvertiere Koordinaten zu float
                    latitude = float(latitude_str)
                    longitude = float(longitude_str)
                    
                    # Validiere Koordinaten (Schweiz liegt etwa zwischen 45.8-47.8°N und 5.9-10.5°E)
                    if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
                        print(f"[WARNUNG] Ungültige Koordinaten in Zeile {row_num}: {name} ({latitude}, {longitude})")
                        continue
                    
                    locations.append({
                        'name': name,
                        'latitude': latitude,
                        'longitude': longitude
                    })
                    
                except ValueError as e:
                    print(f"[WARNUNG] Fehler beim Parsen der Zeile {row_num}: {e}")
                    continue
                except Exception as e:
                    print(f"[WARNUNG] Unerwarteter Fehler in Zeile {row_num}: {e}")
                    continue
        
        print(f"[INFO] {len(locations)} Standorte aus CSV-Datei geladen")
        return locations
        
    except Exception as e:
        print(f"[FEHLER] Fehler beim Lesen der CSV-Datei: {e}")
        return locations


def get_temperature_forecast_for_location(location_name, latitude, longitude):
    """
    Ruft stündliche Wettervorhersage ab (MeteoSwiss ICON-CH Modell)
    Die Anzahl der Tage wird über config.FORECAST_DAYS konfiguriert.
    
    Args:
        location_name: Name des Standorts
        latitude: Breitengrad
        longitude: Längengrad
    
    Returns:
        Dictionary mit Zeitstempeln als Schlüssel und Wetterdaten als Werte.
        Format: {timestamp: {"temperature_2m": float, "cloud_base": float, "precipitation": float, 
        "cloud_cover": float, "cloud_cover_low": float, "cloud_cover_mid": float, 
        "cloud_cover_high": float, "sunshine_duration": float, ...}, ...}
    """
    
    # API-Endpunkt von Open-Meteo mit MeteoSwiss ICON-CH Modell (aus config.py)
    url = config.API_URL
    
    # API-Parameter gemäß Open-Meteo Beispiel für MeteoSwiss ICON-CH
    # Reihenfolge der hourly Parameter ist wichtig und muss mit der Extraktion übereinstimmen
    hourly_params = [
        "temperature_2m",
        "cloud_base",
        "wind_speed_10m",
        "wind_direction_10m",
        "cloud_cover",
        "precipitation",
        "precipitation_probability",
        "cloud_cover_low",
        "cloud_cover_mid",
        "cloud_cover_high",
        "sunshine_duration"
    ]
    
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "models": config.API_MODEL,
        "hourly": ",".join(hourly_params),  # Als komma-separierter String für requests
        "forecast_days": config.FORECAST_DAYS,
        "forecast_hours": config.FORECAST_HOURS,
        "temporal_resolution": config.TEMPORAL_RESOLUTION,
        "past_hours": config.PAST_HOURS,
        "timezone": config.TIMEZONE
    }
    
    try:
        # API-Anfrage
        response = requests.get(url, params=params, timeout=config.API_TIMEOUT)
        response.raise_for_status()
        data = response.json()

    
        # Extrahiere stündliche Daten
        hourly = data.get("hourly", {})
        hourly_times = hourly.get("time", [])
        temperature = hourly.get("temperature_2m", [])
        cloud_base = hourly.get("cloud_base", [])
        wind_speed = hourly.get("wind_speed_10m", [])
        wind_direction = hourly.get("wind_direction_10m", [])
        cloud_cover = hourly.get("cloud_cover", [])
        precipitation = hourly.get("precipitation", [])
        precipitation_probability = hourly.get("precipitation_probability", [])
        cloud_cover_low = hourly.get("cloud_cover_low", [])
        cloud_cover_mid = hourly.get("cloud_cover_mid", [])
        cloud_cover_high = hourly.get("cloud_cover_high", [])
        sunshine_duration = hourly.get("sunshine_duration", [])
        
        if not hourly_times:
            print(f"[WARNUNG] Keine stündlichen Daten verfügbar für {location_name}")
            return
        
        # Erstelle Dictionary mit Zeitstempeln als Schlüssel
        hourly_data = {}
        for i, time_str in enumerate(hourly_times):
            hourly_data[time_str] = {
                "temperature_2m": temperature[i] if i < len(temperature) else None,
                "cloud_base": cloud_base[i] if i < len(cloud_base) else None,
                "wind_speed_10m": wind_speed[i] if i < len(wind_speed) else None,
                "wind_direction_10m": wind_direction[i] if i < len(wind_direction) else None,
                "cloud_cover": cloud_cover[i] if i < len(cloud_cover) else None,
                "precipitation": precipitation[i] if i < len(precipitation) else None,
                "precipitation_probability": precipitation_probability[i] if i < len(precipitation_probability) else None,
                "cloud_cover_low": cloud_cover_low[i] if i < len(cloud_cover_low) else None,
                "cloud_cover_mid": cloud_cover_mid[i] if i < len(cloud_cover_mid) else None,
                "cloud_cover_high": cloud_cover_high[i] if i < len(cloud_cover_high) else None,
                "sunshine_duration": sunshine_duration[i] if i < len(sunshine_duration) else None
            }
        
        # Minimale Info-Ausgabe
        if hourly_data:
            print(f"[INFO] {len(hourly_data)} Zeitstempel für {location_name} abgerufen")
        
        # Gib auch das Dictionary zurück für weitere Verarbeitung
        return hourly_data
        
    except requests.exceptions.RequestException as e:
        print(f"[FEHLER] Fehler beim Abrufen der Daten für {location_name}: {e}")
    except Exception as e:
        print(f"[FEHLER] Unerwarteter Fehler für {location_name}: {e}")


def get_temperature_forecast_for_all_locations():
    """
    Ruft Wettervorhersage für alle Standorte aus der CSV-Datei ab.
    Speichert alle Daten in einer einzigen JSON-Datei.
    """
    locations = load_locations_from_csv(config.CSV_FILE_PATH)
    
    if not locations:
        print("[FEHLER] Keine Standorte gefunden. Bitte überprüfen Sie die CSV-Datei.")
        return
    
    successful = 0
    failed = 0
    all_weather_data = {}
    
    for idx, location in enumerate(locations, 1):
        print(f"[{idx}/{len(locations)}] Verarbeite Standort: {location['name']}")
        try:
            hourly_data = get_temperature_forecast_for_location(
                location['name'],
                location['latitude'],
                location['longitude']
            )
            if hourly_data:
                all_weather_data[location['name']] = {
                    'latitude': location['latitude'],
                    'longitude': location['longitude'],
                    'hourly_data': hourly_data
                }
            successful += 1
        except Exception as e:
            print(f"[FEHLER] Fehler beim Verarbeiten von {location['name']}: {e}")
            failed += 1
    
    # Speichere alle Wetterdaten in einer einzigen JSON-Datei
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    json_filename = os.path.join(config.OUTPUT_DIR, config.WEATHER_JSON_FILENAME)
    with open(json_filename, 'w', encoding='utf-8') as f:
        json.dump(all_weather_data, f, indent=2, ensure_ascii=False)
    print(f"\n[INFO] Alle Wetterdaten gespeichert in: {json_filename}")
    print(f"[INFO] Erfolgreich: {successful}, Fehlgeschlagen: {failed}")


if __name__ == "__main__":
    get_temperature_forecast_for_all_locations()

