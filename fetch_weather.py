#!/usr/bin/env python3
"""Einfaches Skript zur Abfrage der Wettervorhersage von MeteoSwiss"""

import requests
import json
import os
import config


def get_temperature_forecast_for_location(location_name, latitude, longitude):
    """Ruft stündliche Wettervorhersage ab (MeteoSwiss ICON-CH Modell)"""
    
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "models": config.API_MODEL,
        "hourly": ",".join(config.HOURLY_PARAMS),
        "forecast_days": config.FORECAST_DAYS,
        "timezone": config.TIMEZONE
    }
    
    try:
        response = requests.get(config.API_URL, params=params, timeout=config.API_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        
        hourly = data.get("hourly", {})
        hourly_times = hourly.get("time", [])
        
        if not hourly_times:
            print(f"[WARNUNG] Keine stündlichen Daten verfügbar für {location_name}")
            return None
        
        hourly_data = {}
        for i, time_str in enumerate(hourly_times):
            hourly_data[time_str] = {
                "temperature_2m": hourly.get("temperature_2m", [None])[i] if i < len(hourly.get("temperature_2m", [])) else None,
                "cloud_base": hourly.get("cloud_base", [None])[i] if i < len(hourly.get("cloud_base", [])) else None,
                "wind_speed_10m": hourly.get("wind_speed_10m", [None])[i] if i < len(hourly.get("wind_speed_10m", [])) else None,
                "wind_direction_10m": hourly.get("wind_direction_10m", [None])[i] if i < len(hourly.get("wind_direction_10m", [])) else None,
                "wind_gusts_10m": hourly.get("wind_gusts_10m", [None])[i] if i < len(hourly.get("wind_gusts_10m", [])) else None,
                "cloud_cover": hourly.get("cloud_cover", [None])[i] if i < len(hourly.get("cloud_cover", [])) else None,
                "precipitation": hourly.get("precipitation", [None])[i] if i < len(hourly.get("precipitation", [])) else None,
                "rain": hourly.get("rain", [None])[i] if i < len(hourly.get("rain", [])) else None,
                "precipitation_probability": hourly.get("precipitation_probability", [None])[i] if i < len(hourly.get("precipitation_probability", [])) else None,
                "cloud_cover_low": hourly.get("cloud_cover_low", [None])[i] if i < len(hourly.get("cloud_cover_low", [])) else None,
                "cloud_cover_mid": hourly.get("cloud_cover_mid", [None])[i] if i < len(hourly.get("cloud_cover_mid", [])) else None,
                "cloud_cover_high": hourly.get("cloud_cover_high", [None])[i] if i < len(hourly.get("cloud_cover_high", [])) else None,
                "sunshine_duration": hourly.get("sunshine_duration", [None])[i] if i < len(hourly.get("sunshine_duration", [])) else None,
                "cape": hourly.get("cape", [None])[i] if i < len(hourly.get("cape", [])) else None
            }
        
        print(f"[INFO] {len(hourly_data)} Zeitstempel für {location_name} abgerufen")
        return hourly_data
        
    except requests.exceptions.RequestException as e:
        print(f"[FEHLER] Fehler beim Abrufen der Daten für {location_name}: {e}")
        return None
    except Exception as e:
        print(f"[FEHLER] Unerwarteter Fehler für {location_name}: {e}")
        return None


def fetch_weather_for_location(save_to_file=True, output_path=None):
    """
    Ruft Wettervorhersage für den konfigurierten Standort ab.
    
    Args:
        save_to_file: Ob die Daten in eine Datei gespeichert werden sollen
        output_path: Optionaler Pfad für die Ausgabedatei (Standard: config.OUTPUT_DIR/config.WEATHER_JSON_FILENAME)
    
    Returns:
        Dictionary mit Wetterdaten oder None bei Fehler
    """
    location = config.LOCATION
    
    print(f"Verarbeite Standort: {location['name']}")
    try:
        hourly_data = get_temperature_forecast_for_location(
            location['name'],
            location['latitude'],
            location['longitude']
        )
        
        if not hourly_data:
            print("[FEHLER] Keine Wetterdaten abgerufen.")
            return None
        
        location_entry = {
            'latitude': location['latitude'],
            'longitude': location['longitude'],
            'hourly_data': hourly_data
        }
        
        # Füge optionale Felder hinzu, falls vorhanden
        if 'typ' in location:
            location_entry['typ'] = location['typ']
        if 'fluggebiet' in location:
            location_entry['fluggebiet'] = location['fluggebiet']
        if 'windrichtung' in location:
            location_entry['windrichtung'] = location['windrichtung']
        if 'bemerkung' in location:
            location_entry['bemerkung'] = location['bemerkung']
        
        # Speichere als Dictionary mit Standortname als Key
        all_weather_data = {location['name']: location_entry}
        print(all_weather_data)
        
        # Speichere in Datei falls gewünscht
        if save_to_file:
            if output_path is None:
                json_filename = str(config.get_weather_json_path())
            else:
                json_filename = output_path
                os.makedirs(os.path.dirname(json_filename), exist_ok=True)
            
            with open(json_filename, 'w', encoding='utf-8') as f:
                json.dump(all_weather_data, f, indent=2, ensure_ascii=False)
            
            print(f"\n[INFO] Wetterdaten gespeichert in: {json_filename}")
        
        print(f"[INFO] Standort erfolgreich verarbeitet: {location['name']}")
        return all_weather_data
        
    except Exception as e:
        print(f"[FEHLER] Fehler beim Verarbeiten von {location['name']}: {e}")
        return None


if __name__ == "__main__":
    fetch_weather_for_location()
