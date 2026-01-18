#!/usr/bin/env python3
"""Einfaches Skript zur Abfrage der Wettervorhersage von MeteoSwiss"""

import requests
import json
import os
import config


def get_temperature_forecast_for_location(location_name, latitude, longitude):
    """Ruft stündliche Wettervorhersage ab (Hybrid-Modell: ICON-CH1 + Seamless Fallback)"""
    
    # 1. Haupt-Request (ICON-CH1 für hohe Präzision & Cloud Base)
    params_ch1 = {
        "latitude": latitude,
        "longitude": longitude,
        "models": "meteoswiss_icon_ch1",
        "hourly": ",".join(config.HOURLY_PARAMS),
        "forecast_days": config.FORECAST_DAYS,
        "timezone": config.TIMEZONE
    }
    
    # 2. Fallback-Request (Seamless für 3. Tag / Lücken)
    params_seamless = {
        "latitude": latitude,
        "longitude": longitude,
        "models": "icon_seamless",
        "hourly": ",".join(config.HOURLY_PARAMS),
        "forecast_days": config.FORECAST_DAYS,
        "timezone": config.TIMEZONE
    }
    
    try:
        # Abrufen beider Modelle
        print(f"[INFO] Rufe ICON-CH1 Daten ab für {location_name}...")
        resp_ch1 = requests.get(config.API_URL, params=params_ch1, timeout=config.API_TIMEOUT)
        resp_ch1.raise_for_status()
        data_ch1 = resp_ch1.json()
        
        print(f"[INFO] Rufe Seamless Fallback Daten ab für {location_name}...")
        resp_sl = requests.get(config.API_URL, params=params_seamless, timeout=config.API_TIMEOUT)
        resp_sl.raise_for_status()
        data_sl = resp_sl.json()
        
        hourly_ch1 = data_ch1.get("hourly", {})
        hourly_sl = data_sl.get("hourly", {})
        
        times_sl = hourly_sl.get("time", [])
        if not times_sl:
            print(f"[WARNUNG] Keine Seamless Daten verfügbar für {location_name}")
            return None
            
        # Merging Logik: Initialisiere mit Seamless (für alle 3 Tage)
        hourly_data = {}
        for i, time_str in enumerate(times_sl):
            # Initialer Stand aus Seamless
            entry = {}
            for param in config.HOURLY_PARAMS:
                val = hourly_sl.get(param, [None])[i] if i < len(hourly_sl.get(param, [])) else None
                entry[param] = val
            hourly_data[time_str] = entry

        # Überschreibe/Ergänze mit ICON-CH1 (wo verfügbar und nicht null)
        times_ch1 = hourly_ch1.get("time", [])
        for i, time_str in enumerate(times_ch1):
            if time_str not in hourly_data:
                continue
                
            for param in config.HOURLY_PARAMS:
                val_ch1 = hourly_ch1.get(param, [None])[i] if i < len(hourly_ch1.get(param, [])) else None
                
                # Wenn ICON-CH1 einen Wert liefert, nimm diesen (da präziser)
                if val_ch1 is not None:
                    hourly_data[time_str][param] = val_ch1
        
        print(f"[INFO] Hybrid-Merge abgeschlossen: {len(hourly_data)} Zeitstempel für {location_name}")
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
