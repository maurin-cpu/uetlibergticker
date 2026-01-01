#!/usr/bin/env python3
"""Einfaches Skript zur Abfrage der Wettervorhersage von Swiss Meteo für die nächsten 5 Tage"""

import requests
import math
import json
import os
import csv
from datetime import datetime
import config

# Pfad zur CSV-Datei mit Standorten
CSV_FILE_PATH = os.path.join("data", "startplaetze_schweiz.csv")

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
    Ruft Wettervorhersage (Temp, Bewölkung, Wind) für die nächsten 5 Tage ab (MeteoSwiss ICON-CH Modell)
    
    Args:
        location_name: Name des Standorts
        latitude: Breitengrad
        longitude: Längengrad
    """
    
    # API-Endpunkt von Open-Meteo mit MeteoSwiss ICON-CH Modell
    url = "https://api.open-meteo.com/v1/forecast"
    
    # API-Parameter mit MeteoSwiss ICON-CH Modell
    # Verwende meteoswiss_icon_ch2 für längere Vorhersagezeiträume
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "models": "meteoswiss_icon_ch2",  # Offizielles MeteoSwiss ICON-CH Modell (CH2 für längere Vorhersage)
        "daily": "temperature_2m_max,temperature_2m_min",
        "hourly": "cloud_base,wind_speed_10m,wind_direction_10m,cloud_cover",  # Stündliche Daten
        "forecast_days": 5,
        "timezone": "Europe/Zurich"
    }
    
    try:
        # API-Anfrage
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        # Speichere JSON-Daten im data Ordner
        os.makedirs(config.OUTPUT_DIR, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        location_safe = location_name.replace(" ", "_").replace(".", "")
        json_filename = f"{config.OUTPUT_DIR}/wetter_{location_safe}_{timestamp}.json"
        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"[INFO] JSON-Daten gespeichert: {json_filename}")
        
        # Extrahiere tägliche Daten
        daily = data.get("daily", {})
        times = daily.get("time", [])
        temps_max = daily.get("temperature_2m_max", [])
        temps_min = daily.get("temperature_2m_min", [])
        
        # Extrahiere stündliche Daten
        hourly = data.get("hourly", {})
        hourly_times = hourly.get("time", [])
        cloud_base = hourly.get("cloud_base", [])
        wind_speed = hourly.get("wind_speed_10m", [])
        wind_direction = hourly.get("wind_direction_10m", [])
        cloud_cover = hourly.get("cloud_cover", [])
        
        if not times or not temps_max or not temps_min:
            print(f"[WARNUNG] Keine Daten verfügbar für {location_name}")
            return
        
        # Hilfsfunktion für Durchschnittswerte
        def calc_avg(values_dict):
            """Berechnet Durchschnittswerte aus einem Dictionary mit Listen"""
            result = {}
            for date_str, values in values_dict.items():
                if values:
                    valid_values = [v for v in values if v is not None]
                    if valid_values:
                        result[date_str] = sum(valid_values) / len(valid_values)
            return result
        
        # Gruppiere alle stündlichen Daten nach Tagen
        cloud_base_by_day = {}
        wind_speed_by_day = {}
        wind_direction_by_day = {}
        cloud_cover_by_day = {}
        
        for i, time_str in enumerate(hourly_times):
            dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
            date_str = dt.strftime("%Y-%m-%d")
            
            # Bewölkungshöhe
            cb = cloud_base[i] if i < len(cloud_base) else None
            if cb is not None:
                if date_str not in cloud_base_by_day:
                    cloud_base_by_day[date_str] = []
                cloud_base_by_day[date_str].append(cb)
            
            # Windgeschwindigkeit
            ws = wind_speed[i] if i < len(wind_speed) else None
            if ws is not None:
                if date_str not in wind_speed_by_day:
                    wind_speed_by_day[date_str] = []
                wind_speed_by_day[date_str].append(ws)
            
            # Windrichtung
            wd = wind_direction[i] if i < len(wind_direction) else None
            if wd is not None:
                if date_str not in wind_direction_by_day:
                    wind_direction_by_day[date_str] = []
                wind_direction_by_day[date_str].append(wd)
            
            # Bewölkungsgrad
            cc = cloud_cover[i] if i < len(cloud_cover) else None
            if cc is not None:
                if date_str not in cloud_cover_by_day:
                    cloud_cover_by_day[date_str] = []
                cloud_cover_by_day[date_str].append(cc)
        
        # Berechne Durchschnittswerte pro Tag
        cloud_base_avg = calc_avg(cloud_base_by_day)
        wind_speed_avg = calc_avg(wind_speed_by_day)
        cloud_cover_avg = calc_avg(cloud_cover_by_day)
        
        # Berechne dominante Windrichtung pro Tag (zirkulärer Durchschnitt)
        wind_direction_dominant = {}
        for date_str, values in wind_direction_by_day.items():
            if values:
                valid_values = [v for v in values if v is not None]
                if valid_values:
                    # Berechne Durchschnitt der Windrichtung (zirkulär)
                    sin_sum = sum(math.sin(math.radians(v)) for v in valid_values)
                    cos_sum = sum(math.cos(math.radians(v)) for v in valid_values)
                    avg_degrees = math.degrees(math.atan2(sin_sum / len(valid_values), 
                                                          cos_sum / len(valid_values)))
                    if avg_degrees < 0:
                        avg_degrees += 360
                    wind_direction_dominant[date_str] = avg_degrees
        
        # Zeige Temperaturvorhersage und Bewölkungshöhe
        print(f"\n{'='*60}")
        print(f"WETTERVORHERSAGE - NÄCHSTE 5 TAGE")
        print(f"MeteoSwiss ICON-CH Modell")
        print(f"Standort: {location_name} ({latitude}, {longitude})")
        print(f"{'='*60}\n")
        
        # Zeige die ersten 5 Tage an
        for i in range(min(5, len(times))):
            date_str = times[i]
            temp_max = temps_max[i] if i < len(temps_max) and temps_max[i] is not None else None
            temp_min = temps_min[i] if i < len(temps_min) and temps_min[i] is not None else None
            cb_avg = cloud_base_avg.get(date_str)
            
            if temp_max is not None and temp_min is not None:
                avg_temp = (temp_max + temp_min) / 2
                # Formatiere Datum schöner
                dt_obj = datetime.strptime(date_str, "%Y-%m-%d")
                date_display = dt_obj.strftime("%d.%m.%Y")
                
                # Sammle alle Informationen
                info_parts = [f"{date_display}:"]
                info_parts.append(f"Temp: {avg_temp:.1f}°C (Min: {temp_min:.1f}°C, Max: {temp_max:.1f}°C)")
                
                # Bewölkungshöhe
                cb_avg = cloud_base_avg.get(date_str)
                if cb_avg is not None:
                    info_parts.append(f"Bewölkungshöhe: {cb_avg:.0f}m")
                else:
                    info_parts.append("Bewölkungshöhe: N/A")
                
                # Bewölkungsgrad
                cc_avg = cloud_cover_avg.get(date_str)
                if cc_avg is not None:
                    info_parts.append(f"Bewölkungsgrad: {cc_avg:.0f}%")
                else:
                    info_parts.append("Bewölkungsgrad: N/A")
                
                # Windgeschwindigkeit (API gibt m/s zurück, umrechnen zu km/h)
                ws_avg = wind_speed_avg.get(date_str)
                if ws_avg is not None:
                    ws_kmh = ws_avg * 3.6  # m/s zu km/h umrechnen
                    info_parts.append(f"Wind: {ws_kmh:.1f}km/h")
                else:
                    info_parts.append("Wind: N/A")
                
                # Windrichtung
                wd_avg = wind_direction_dominant.get(date_str)
                if wd_avg is not None:
                    info_parts.append(f"Windrichtung: {wd_avg:.0f}°")
                else:
                    info_parts.append("Windrichtung: N/A")
                
                print(" | ".join(info_parts))
        
        print(f"\n{'='*60}\n")
        
    except requests.exceptions.RequestException as e:
        print(f"[FEHLER] Fehler beim Abrufen der Daten für {location_name}: {e}")
    except Exception as e:
        print(f"[FEHLER] Unerwarteter Fehler für {location_name}: {e}")


def get_temperature_forecast_for_all_locations():
    """
    Ruft Wettervorhersage für alle Standorte aus der CSV-Datei ab.
    """
    locations = load_locations_from_csv(CSV_FILE_PATH)
    
    if not locations:
        print("[FEHLER] Keine Standorte gefunden. Bitte überprüfen Sie die CSV-Datei.")
        return
    
    print(f"\n{'='*60}")
    print(f"WETTERVORHERSAGE FÜR {len(locations)} STANDORTE")
    print(f"{'='*60}\n")
    
    successful = 0
    failed = 0
    
    for idx, location in enumerate(locations, 1):
        print(f"\n[{idx}/{len(locations)}] Verarbeite Standort: {location['name']}")
        try:
            get_temperature_forecast_for_location(
                location['name'],
                location['latitude'],
                location['longitude']
            )
            successful += 1
        except Exception as e:
            print(f"[FEHLER] Fehler beim Verarbeiten von {location['name']}: {e}")
            failed += 1
    
    print(f"\n{'='*60}")
    print(f"ZUSAMMENFASSUNG")
    print(f"{'='*60}")
    print(f"Erfolgreich: {successful}")
    print(f"Fehlgeschlagen: {failed}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    get_temperature_forecast_for_all_locations()

