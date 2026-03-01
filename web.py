#!/usr/bin/env python3
"""
Web-Interface Server für Uetliberg Ticker mit Zeitlinien-Diagrammen
Flask-basiertes Interface mit D3.js Visualisierung und LLM-Auswertung
"""

import json
import os
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template, jsonify, request, send_file
import config
from thermik_calculator import calculate_thermal_profile, calculate_dewpoint
from config import (
    FLIGHT_HOURS_START,
    FLIGHT_HOURS_END,
    LOCATION,
    PRESSURE_LEVELS,
    get_weather_json_path,
    get_evaluations_json_path
)

# Original-Werte für Reset-Funktion speichern
import copy
_ORIGINAL_CONFIG = {
    'LOCATION': copy.deepcopy(config.LOCATION),
    'API_URL': config.API_URL,
    'API_MODEL': config.API_MODEL,
    'API_TIMEOUT': config.API_TIMEOUT,
    'FORECAST_DAYS': config.FORECAST_DAYS,
    'TIMEZONE': config.TIMEZONE,
    'FLIGHT_HOURS_START': config.FLIGHT_HOURS_START,
    'FLIGHT_HOURS_END': config.FLIGHT_HOURS_END,
    'LLM_SYSTEM_PROMPT': config.LLM_SYSTEM_PROMPT,
    'LLM_USER_PROMPT_TEMPLATE': config.LLM_USER_PROMPT_TEMPLATE,
}

# Lade .env Datei explizit
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from email_notifier import EmailNotifier
except ImportError:
    EmailNotifier = None

try:
    from fetch_weather import fetch_weather_for_location
except ImportError:
    fetch_weather_for_location = None

try:
    from instantdb_helper import (
        save_weather_data as instantdb_save,
        load_weather_data as instantdb_load,
        save_evaluation_data as instantdb_save_eval,
        load_evaluation_data as instantdb_load_eval,
        load_region_weather as instantdb_load_region
    )
except ImportError:
    instantdb_save = None
    instantdb_load = None
    instantdb_save_eval = None
    instantdb_load_eval = None
    instantdb_load_region = None

# Globaler Cache für Wetterdaten (für Vercel Instanzen)
CACHED_WEATHER_DATA = None
LAST_FETCH_TIME = 0
CACHE_DURATION = 300  # 5 Minuten Cache

# Stelle sicher, dass Flask das templates-Verzeichnis findet
# Für Vercel: Verwende absoluten Pfad zum Projekt-Root
template_dir = Path(__file__).parent / 'templates'
if not template_dir.exists():
    # Fallback: Falls templates/ nicht existiert, verwende aktuelles Verzeichnis
    template_dir = Path(__file__).parent

app = Flask(__name__, template_folder=str(template_dir))


def load_weather_data():
    """
    Laedt Wetterdaten.
    1. In-Memory Cache (weniger als 5 Min alt)
    2. InstantDB (einzige Datenquelle)
    3. Keine Daten - Meldung
    """
    global CACHED_WEATHER_DATA, LAST_FETCH_TIME
    import logging
    import time
    logger = logging.getLogger(__name__)
    
    current_time = time.time()
    
    # 1. Pruefe In-Memory Cache
    if CACHED_WEATHER_DATA and (current_time - LAST_FETCH_TIME < CACHE_DURATION):
        logger.info("Verwende gecachte Wetterdaten (In-Memory)")
        if isinstance(CACHED_WEATHER_DATA, dict):
            CACHED_WEATHER_DATA['_debug_source'] = "CACHE_MEMORY"
            CACHED_WEATHER_DATA['_debug_timestamp'] = str(LAST_FETCH_TIME)
        return CACHED_WEATHER_DATA
    
    # 2. InstantDB (einzige Datenquelle)
    if instantdb_load:
        try:
            logger.info("Lade Wetterdaten aus InstantDB...")
            db_data = instantdb_load()
            if db_data:
                # Extrahiere Uetliberg Daten
                found_location = None
                for key in db_data.keys():
                    if 'uetliberg' in key.lower() or 'balderen' in key.lower():
                        found_location = key
                        break
                
                if found_location:
                    CACHED_WEATHER_DATA = db_data[found_location]
                    if isinstance(CACHED_WEATHER_DATA, dict):
                        CACHED_WEATHER_DATA['_debug_source'] = 'INSTANTDB'
                    LAST_FETCH_TIME = current_time
                    logger.info("Wetterdaten aus InstantDB geladen")
                    return CACHED_WEATHER_DATA
                elif 'hourly_data' in db_data:
                    CACHED_WEATHER_DATA = db_data
                    if isinstance(CACHED_WEATHER_DATA, dict):
                        CACHED_WEATHER_DATA['_debug_source'] = 'INSTANTDB'
                    LAST_FETCH_TIME = current_time
                    logger.info("Wetterdaten aus InstantDB geladen")
                    return CACHED_WEATHER_DATA
        except Exception as e:
            logger.error(f"InstantDB Laden fehlgeschlagen: {e}")
    
    # 3. Keine Daten vorhanden
    logger.info("Keine Wetterdaten in InstantDB. Bitte 'Daten aktualisieren' klicken.")
    return {
        'hourly_data': {},
        '_debug_source': 'NO_DATA',
        '_empty': True
    }



def filter_flight_hours(hourly_data):
    """Filtert Stunden-Daten auf Flugstunden."""
    filtered = {}
    for timestamp, data in hourly_data.items():
        try:
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            hour = dt.hour
            if FLIGHT_HOURS_START <= hour < FLIGHT_HOURS_END:
                filtered[timestamp] = data
        except Exception:
            continue
    return filtered


def group_by_days(hourly_data):
    """Gruppiert Stunden-Daten nach Tagen."""
    days_data = {}
    for timestamp, data in hourly_data.items():
        try:
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            date_key = dt.strftime("%Y-%m-%d")
            if date_key not in days_data:
                days_data[date_key] = {}
            days_data[date_key][timestamp] = data
        except Exception:
            continue
    return days_data


def format_data_for_charts(hourly_data, pressure_level_data=None, elevation_ref=None):
    """Formatiert Daten für D3.js Charts inkl. Physik."""
    chart_data = {
        'wind': [],
        'precipitation': [],
        'thermik': [],
        'cloudbase': []
    }
    
    sorted_times = sorted(hourly_data.keys())
    
    for timestamp in sorted_times:
        data = hourly_data[timestamp]
        try:
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            time_str = dt.isoformat()
            
            # Wind-Daten
            # Wetterdaten enthalten bereits die Bewegungsrichtung (wohin Wind weht)
            # 0° = Norden, 90° = Osten, 180° = Süden, 270° = Westen
            wind_speed = data.get('wind_speed_10m')
            wind_gusts = data.get('wind_gusts_10m')
            wind_direction = data.get('wind_direction_10m')
            if wind_speed is not None and wind_direction is not None:
                chart_data['wind'].append({
                    'time': time_str,
                    'speed': wind_speed,
                    'gusts': wind_gusts if wind_gusts is not None else wind_speed,
                    'direction': wind_direction  # Bewegungsrichtung (wohin Wind weht)
                })
            
            # Niederschlags-Daten
            precipitation = data.get('precipitation', 0)
            precip_prob = data.get('precipitation_probability', 0)
            if precipitation is not None:
                chart_data['precipitation'].append({
                    'time': time_str,
                    'amount': precipitation,
                    'probability': precip_prob if precip_prob is not None else 0
                })
            
            # Thermik-Daten (CAPE & Proxy)
            cape = data.get('cape', 0)
            
            # Berechne Thermik-Proxy Profil für D3 Charts
            p_levels = []
            if pressure_level_data and timestamp in pressure_level_data:
                for level in PRESSURE_LEVELS:
                    h_val = pressure_level_data[timestamp].get(f'geopotential_height_{level}hPa')
                    t_val = pressure_level_data[timestamp].get(f'temperature_{level}hPa')
                    if h_val is not None and t_val is not None:
                        p_levels.append({'pressure': level, 'height': h_val, 'temp': t_val})
                        
            surf_temp = data.get('temperature_2m')
            surf_dew = calculate_dewpoint(surf_temp, data.get('relative_humidity_2m', 50))

            # Referenzhöhe: Parameter > LOCATION-Config
            elev_ref = elevation_ref if elevation_ref is not None else LOCATION.get('elevation_ref', 850.0)

            therm_climb = 0
            therm_rating = 0
            therm_max_h = None
            therm_diagnostics = {}
            therm_warnings = []
            if surf_temp is not None and p_levels:
                therm = calculate_thermal_profile(
                    surface_temp=surf_temp,
                    surface_dewpoint=surf_dew,
                    elevation_m=elev_ref,
                    pressure_levels_data=p_levels,
                    boundary_layer_height_agl=data.get('boundary_layer_height'),
                    sunshine_duration_s=data.get('sunshine_duration'),
                    surface_sensible_heat_flux=data.get('surface_sensible_heat_flux'),
                    surface_latent_heat_flux=data.get('surface_latent_heat_flux'),
                    shortwave_radiation=data.get('shortwave_radiation'),
                )
                if 'error' not in therm:
                    therm_climb = therm['climb_rate']
                    therm_rating = therm['rating']
                    therm_max_h = therm['max_height']
                    therm_diagnostics = therm.get('diagnostics', {})
                    therm_warnings = therm.get('data_warnings', [])

            if cape is not None:
                chart_data['thermik'].append({
                    'time': time_str,
                    'cape': cape,
                    'climb_rate': therm_climb,
                    'rating': therm_rating,
                    'max_height': therm_max_h,
                    'diagnostics': therm_diagnostics,
                    'data_warnings': therm_warnings,
                })
            
            # Wolkenbasis-Daten
            cloud_base = data.get('cloud_base')
            cloud_cover = data.get('cloud_cover')
            
            if cloud_base is not None or cloud_cover is not None:
                chart_data['cloudbase'].append({
                    'time': time_str,
                    'height': cloud_base,
                    'cover': cloud_cover
                })
        except Exception:
            continue
    
    return chart_data


def format_altitude_wind_for_charts(pressure_level_data):
    """Formatiert Höhenwind-Daten für D3.js Altitude Profile Chart."""
    chart_data = {'profiles': []}
    sorted_times = sorted(pressure_level_data.keys())

    for timestamp in sorted_times:
        data = pressure_level_data[timestamp]
        try:
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            profile = {'time': dt.isoformat(), 'levels': []}

            for level in PRESSURE_LEVELS:
                height = data.get(f'geopotential_height_{level}hPa')
                wind_speed = data.get(f'wind_speed_{level}hPa')
                wind_direction = data.get(f'wind_direction_{level}hPa')
                temperature = data.get(f'temperature_{level}hPa')

                if height is not None and wind_speed is not None:
                    profile['levels'].append({
                        'pressure': level,
                        'altitude': height,
                        'wind_speed': wind_speed,
                        'wind_direction': wind_direction if wind_direction is not None else 0,
                        'temperature': temperature if temperature is not None else 0
                    })

            if len(profile['levels']) >= 3:
                chart_data['profiles'].append(profile)
        except Exception:
            continue

    return chart_data


def get_evaluation_data():
    """Laedt LLM-Auswertung ausschliesslich aus InstantDB."""
    import logging
    logger = logging.getLogger(__name__)
    
    # InstantDB (einzige Datenquelle)
    if instantdb_load_eval:
        try:
            logger.info("Lade Evaluierungen aus InstantDB...")
            db_eval = instantdb_load_eval()
            if db_eval:
                evaluations_list = db_eval.get('evaluations', [])
                evaluations_by_date = {}
                for result in evaluations_list:
                    date = result.get('date')
                    if date:
                        evaluations_by_date[date] = result
                if evaluations_by_date:
                    logger.info("Evaluierungen aus InstantDB geladen")
                    return evaluations_by_date
        except Exception as e:
            logger.error(f"InstantDB Evaluierung-Laden fehlgeschlagen: {e}")
    
    logger.info("Keine Evaluierungen in InstantDB. Bitte 'Daten aktualisieren' klicken.")
    return {}


@app.route('/')
def index():
    """Hauptroute für das Web-Interface."""
    return render_template('weather_timeline.html')


@app.route('/meteo')
def meteo_grafik():
    """Meteo-Grafik Seite mit Höhenwind-Matrix."""
    return render_template('meteo_grafik.html')


@app.route('/config')
def config_page():
    """Konfigurationsseite."""
    return render_template('config.html')


@app.route('/emagramm')
def emagramm_page():
    """Rendert die Emagramm Seite."""
    return render_template('emagramm.html')


@app.route('/raw-data')
def raw_data_page():
    """Zeigt die unformatierten Open-Meteo Rohdaten an."""
    return render_template('raw_data.html')


@app.route('/regions')
def regions_page():
    """Rendert die interaktive Schweizer Thermik-Landkarte."""
    return render_template('regions.html')


@app.route('/api/regions-data')
def api_regions_data():
    """Gibt die aggregierten Regionen-Daten zurück."""
    try:
        path = config.get_data_dir() / "regions_forecast.json"
        if not path.exists():
            return jsonify({'error': 'Noch keine Regionen-Daten vorhanden. Bitte fetch_regions.py ausführen.'}), 404
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/region-weather/<region_id>')
def api_region_weather(region_id):
    """API-Endpoint fuer Wetterdaten einer einzelnen Region (Meteogramm)."""
    try:
        # 1. Region in config.REGIONS finden
        region = None
        for r in config.REGIONS:
            if r['id'] == region_id:
                region = r
                break
        if not region:
            return jsonify({'success': False, 'error': f'Region "{region_id}" nicht gefunden'}), 404

        # 2. Rohe Wetterdaten aus InstantDB laden
        if not instantdb_load_region:
            return jsonify({'success': False, 'error': 'InstantDB nicht verfuegbar'}), 500

        raw = instantdb_load_region(region_id)
        if not raw:
            return jsonify({'success': False, 'error': f'Keine Wetterdaten fuer Region "{region_id}"'}), 404

        hourly_data = raw.get('hourly_data', {})
        pressure_level_data = raw.get('pressure_level_data', {})
        elev_ref = region.get('elevation_ref', 800)

        # 3. Filtern + Gruppieren
        flight_hours_data = filter_flight_hours(hourly_data)
        days_data = group_by_days(flight_hours_data)

        flight_hours_pl = filter_flight_hours(pressure_level_data)
        days_pl_data = group_by_days(flight_hours_pl)

        # 4. Formatieren
        weather_days = {}
        for date_key, day_hourly in days_data.items():
            weather_days[date_key] = format_data_for_charts(
                day_hourly, days_pl_data.get(date_key, {}), elevation_ref=elev_ref
            )

        alt_wind_days = {}
        for date_key, day_pl in days_pl_data.items():
            alt_wind_days[date_key] = format_altitude_wind_for_charts(day_pl)

        sorted_dates = sorted(set(list(weather_days.keys()) + list(alt_wind_days.keys())))

        return jsonify({
            'success': True,
            'location': {
                'name': region['name'],
                'latitude': region['lat'],
                'longitude': region['lon'],
                'elevation_ref': elev_ref,
            },
            'weather': {
                'days': weather_days,
                'dates': sorted_dates,
            },
            'altitude_wind': {
                'days': alt_wind_days,
                'dates': sorted_dates,
            }
        })
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Fehler bei Region-Weather '{region_id}': {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/data/regionen_polygone_mapped.geojson')
def regions_polygons_geojson():
    """Serviert die gemappten Regionen-Polygone (mit Properties aus Referenzpunkten)."""
    geojson_path = Path(__file__).parent / 'data' / 'regionen_polygone_mapped.geojson'
    if not geojson_path.exists():
        return jsonify({'error': 'regionen_polygone_mapped.geojson nicht gefunden. Bitte map_polygons.py ausfuehren.'}), 404
    return send_file(str(geojson_path), mimetype='application/geo+json')


@app.route('/data/regionen_referenzpunkte.geojson')
def regions_reference_points_geojson():
    """Serviert die Referenzpunkte (Startplaetze) als GeoJSON."""
    geojson_path = Path(__file__).parent / 'data' / 'regionen_referenzpunkte.geojson'
    if not geojson_path.exists():
        return jsonify({'error': 'regionen_referenzpunkte.geojson nicht gefunden'}), 404
    return send_file(str(geojson_path), mimetype='application/geo+json')


@app.route('/data/swiss_cantons.geojson')
def swiss_cantons_geojson():
    """Serviert die GeoJSON-Datei mit den Schweizer Kantonsgrenzen (Overlay)."""
    geojson_path = Path(__file__).parent / 'data' / 'swiss_cantons.geojson'
    if not geojson_path.exists():
        return jsonify({'error': 'Kantons-GeoJSON nicht gefunden'}), 404
    return send_file(str(geojson_path), mimetype='application/geo+json')


@app.route('/api/raw-data')
def api_raw_data():
    """Gibt die reinen Wetterdaten (Rohdaten) als JSON zurück."""
    try:
        data = load_weather_data()
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/emagramm-data')
def api_emagramm_data():
    """Gibt Daten für das Emagramm zurück, inkl. berechnetem Taupunkt."""
    import requests
    import math
    from datetime import datetime
    
    try:
        lat = 45.2517
        lon = 0.824
        
        pressure_levels = [1000, 975, 950, 925, 900, 850, 800, 700, 600, 500]
        
        hourly_vars = ["temperature_2m", "relative_humidity_2m", "boundary_layer_height", "sunshine_duration"]
        for level in pressure_levels:
            hourly_vars.append(f"temperature_{level}hPa")
            hourly_vars.append(f"relative_humidity_{level}hPa")
            
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "hourly": ",".join(hourly_vars),
            "timezone": "auto",
            "forecast_days": 1
        }
        
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        now_str = datetime.now().strftime("%Y-%m-%dT%H:00")
        try:
            time_index = data["hourly"]["time"].index(now_str)
        except ValueError:
            time_index = 0
            
        results = []
        
        # Magnus formel für Taupunkt
        # constants
        A = 17.625
        B = 243.04
        
        for level in pressure_levels:
            temp_val = data["hourly"][f"temperature_{level}hPa"][time_index]
            rh_val = data["hourly"][f"relative_humidity_{level}hPa"][time_index]
            
            # calculate dewpoint
            alpha = math.log(rh_val/100.0) + ((A * temp_val) / (B + temp_val))
            dewpoint_val = (B * alpha) / (A - alpha)
            
            results.append({
                "pressure": level,
                "temperature": temp_val,
                "dewpoint": dewpoint_val,
                "relative_humidity": rh_val
            })
            
        # Berechne Thermik-Kurve
        surf_temp = data["hourly"]["temperature_2m"][time_index]
        surf_rh = data["hourly"]["relative_humidity_2m"][time_index]
        surf_dew = calculate_dewpoint(surf_temp, surf_rh)
        
        p_levels = []
        for r in results:
            p_levels.append({'pressure': r['pressure'], 'temp': r['temperature']})
            
        therm = calculate_thermal_profile(
            surface_temp=surf_temp,
            surface_dewpoint=surf_dew,
            elevation_m=LOCATION.get('elevation_ref', 850),
            pressure_levels_data=p_levels,
            boundary_layer_height_agl=data["hourly"]["boundary_layer_height"][time_index],
            sunshine_duration_s=data["hourly"]["sunshine_duration"][time_index]
        )
            
        return jsonify({
            'success': True, 
            'data': results,
            'thermal': therm,
            'timestamp': data["hourly"]["time"][time_index]
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/config', methods=['GET'])
def api_config_get():
    """Gibt aktuelle Konfigurationswerte als JSON zurück."""
    return jsonify({
        'success': True,
        'config': {
            'location': {
                'name': config.LOCATION.get('name', ''),
                'latitude': config.LOCATION.get('latitude', 0),
                'longitude': config.LOCATION.get('longitude', 0),
                'typ': config.LOCATION.get('typ', ''),
                'fluggebiet': config.LOCATION.get('fluggebiet', ''),
                'windrichtung': config.LOCATION.get('windrichtung', ''),
                'bemerkung': config.LOCATION.get('bemerkung', ''),
            },
            'api': {
                'url': config.API_URL,
                'model': config.API_MODEL,
                'timeout': config.API_TIMEOUT,
                'forecast_days': config.FORECAST_DAYS,
                'timezone': config.TIMEZONE,
            },
            'flight_hours': {
                'start': config.FLIGHT_HOURS_START,
                'end': config.FLIGHT_HOURS_END,
            },
            'llm': {
                'system_prompt': config.LLM_SYSTEM_PROMPT,
                'user_prompt_template': config.LLM_USER_PROMPT_TEMPLATE,
            }
        },
        'original': _ORIGINAL_CONFIG
    })


@app.route('/api/config', methods=['POST'])
def api_config_post():
    """Übernimmt neue Konfigurationswerte (in-memory)."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Keine Daten empfangen'}), 400

        _apply_config(data)
        return jsonify({'success': True, 'message': 'Konfiguration gespeichert (Laufzeit)'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/config/apply', methods=['POST'])
def api_config_apply():
    """Übernimmt Config UND startet den gesamten Pipeline-Prozess."""
    import logging
    logger = logging.getLogger(__name__)
    try:
        data = request.get_json()
        if data:
            _apply_config(data)
            logger.info("Config aktualisiert, starte Pipeline...")

        # Pipeline: Wetter holen → Analyse → Email
        from fetch_weather import fetch_weather_for_location as _fetch
        from location_evaluator import LocationEvaluator

        results = {'steps': {}}

        # 1. Fetch
        weather_path = str(get_weather_json_path())
        weather_data = _fetch(save_to_file=True, output_path=weather_path)
        results['steps']['fetch'] = {'success': bool(weather_data)}

        # Cache invalidieren
        global CACHED_WEATHER_DATA, LAST_FETCH_TIME
        CACHED_WEATHER_DATA = None
        LAST_FETCH_TIME = 0

        # 2. Evaluate & Email
        evaluator = LocationEvaluator(weather_json_path=weather_path)
        analysis_results = evaluator.analyze()
        results['steps']['evaluate'] = {'success': bool(analysis_results)}
        results['steps']['email'] = {'success': True, 'message': 'E-Mail wurde (falls konfiguriert) versendet'}

        results['success'] = True
        return jsonify(results)
    except Exception as e:
        logger.error(f"Config-Apply Pipeline Fehler: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/config/reset', methods=['POST'])
def api_config_reset():
    """Setzt die Konfiguration auf die Originalwerte zurück."""
    try:
        config.LOCATION = copy.deepcopy(_ORIGINAL_CONFIG['LOCATION'])
        config.API_URL = _ORIGINAL_CONFIG['API_URL']
        config.API_MODEL = _ORIGINAL_CONFIG['API_MODEL']
        config.API_TIMEOUT = _ORIGINAL_CONFIG['API_TIMEOUT']
        config.FORECAST_DAYS = _ORIGINAL_CONFIG['FORECAST_DAYS']
        config.TIMEZONE = _ORIGINAL_CONFIG['TIMEZONE']
        config.FLIGHT_HOURS_START = _ORIGINAL_CONFIG['FLIGHT_HOURS_START']
        config.FLIGHT_HOURS_END = _ORIGINAL_CONFIG['FLIGHT_HOURS_END']
        config.LLM_SYSTEM_PROMPT = _ORIGINAL_CONFIG['LLM_SYSTEM_PROMPT']
        config.LLM_USER_PROMPT_TEMPLATE = _ORIGINAL_CONFIG['LLM_USER_PROMPT_TEMPLATE']
        return jsonify({'success': True, 'message': 'Konfiguration auf Originalwerte zurückgesetzt'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


def _apply_config(data):
    """Wendet Konfigurationsdaten auf das config-Modul an."""
    if 'location' in data:
        loc = data['location']
        if 'name' in loc: config.LOCATION['name'] = loc['name']
        if 'latitude' in loc: config.LOCATION['latitude'] = float(loc['latitude'])
        if 'longitude' in loc: config.LOCATION['longitude'] = float(loc['longitude'])
        if 'typ' in loc: config.LOCATION['typ'] = loc['typ']
        if 'fluggebiet' in loc: config.LOCATION['fluggebiet'] = loc['fluggebiet']
        if 'windrichtung' in loc: config.LOCATION['windrichtung'] = loc['windrichtung']
        if 'bemerkung' in loc: config.LOCATION['bemerkung'] = loc['bemerkung']

    if 'api' in data:
        api = data['api']
        if 'url' in api: config.API_URL = api['url']
        if 'model' in api: config.API_MODEL = api['model']
        if 'timeout' in api: config.API_TIMEOUT = int(api['timeout'])
        if 'forecast_days' in api: config.FORECAST_DAYS = int(api['forecast_days'])
        if 'timezone' in api: config.TIMEZONE = api['timezone']

    if 'flight_hours' in data:
        fh = data['flight_hours']
        if 'start' in fh: config.FLIGHT_HOURS_START = int(fh['start'])
        if 'end' in fh: config.FLIGHT_HOURS_END = int(fh['end'])

    if 'llm' in data:
        llm = data['llm']
        if 'system_prompt' in llm: config.LLM_SYSTEM_PROMPT = llm['system_prompt']
        if 'user_prompt_template' in llm: config.LLM_USER_PROMPT_TEMPLATE = llm['user_prompt_template']


@app.route('/api/weather')
def api_weather():
    """API-Endpoint für Wetterdaten."""
    try:
        weather_data = load_weather_data()
        hourly_data = weather_data.get('hourly_data', {})
        pressure_level_data = weather_data.get('pressure_level_data', {})
        flight_hours_data = filter_flight_hours(hourly_data)
        
        # Gruppiere nach Tagen
        days_data = group_by_days(flight_hours_data)
        
        # Formatiere Daten für jeden Tag
        days_formatted = {}
        for date_key, day_hourly_data in days_data.items():
            days_formatted[date_key] = format_data_for_charts(day_hourly_data, pressure_level_data)

        
        # Sortiere Tage chronologisch
        sorted_dates = sorted(days_formatted.keys())
        
        return jsonify({
            'success': True,
            'location': LOCATION,
            'flight_hours': {
                'start': FLIGHT_HOURS_START,
                'end': FLIGHT_HOURS_END
            },
            'days': days_formatted,
            'dates': sorted_dates,
            'total_hours': len(flight_hours_data),
            '_debug_source': weather_data.get('_debug_source'),
            '_debug_path': weather_data.get('_debug_path'),
            '_debug_timestamp': weather_data.get('_debug_timestamp')
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/weather/raw')
def api_weather_raw():
    """API-Endpoint für rohe Wetterdaten (kompatibel mit direktem JSON-Zugriff)."""
    try:
        # Verwende load_weather_data für konsistentes Verhalten (inkl. Fallback & Cache)
        data = load_weather_data()
        return jsonify(data)
    except Exception as e:
        return jsonify({
            'error': str(e)
        }), 500


@app.route('/api/evaluation')
def api_evaluation():
    """API-Endpoint für LLM-Auswertung."""
    try:
        evaluations = get_evaluation_data()
        if evaluations:
            return jsonify({
                'success': True,
                'evaluations': evaluations
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Keine Auswertung verfügbar'
            }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/evaluation/raw')
def api_evaluation_raw():
    """API-Endpoint für rohe Evaluierungsdaten (kompatibel mit direktem JSON-Zugriff)."""
    try:
        # Lade die rohen JSON-Daten direkt
        # Für Vercel: Verwende /tmp falls verfügbar, sonst data/
        evaluations_file = get_evaluations_json_path()
        
        if not evaluations_file or not evaluations_file.exists():
            # Gebe leeres Objekt zurück statt Fehler (Evaluierungen sind optional)
            return jsonify({
                'evaluations': [],
                'last_updated': None
            })
        
        with open(evaluations_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return jsonify(data)
    except Exception as e:
        # Gebe leeres Objekt zurück statt Fehler (Evaluierungen sind optional)
        return jsonify({
            'evaluations': [],
            'last_updated': None
        })


@app.route('/api/altitude-wind')
def api_altitude_wind():
    """API-Endpoint für Höhenwind-Daten (Pressure Level)."""
    try:
        weather_data = load_weather_data()
        pressure_level_data = weather_data.get('pressure_level_data', {})

        if not pressure_level_data:
            return jsonify({
                'success': False,
                'error': 'Keine Höhenwind-Daten verfügbar',
                'pressure_levels': PRESSURE_LEVELS,
                'days': {},
                'dates': []
            })

        # Filtere auf Flugstunden und gruppiere nach Tagen
        flight_hours_pl = filter_flight_hours(pressure_level_data)
        days_pl_data = group_by_days(flight_hours_pl)

        days_formatted = {}
        for date_key, day_pl_data in days_pl_data.items():
            days_formatted[date_key] = format_altitude_wind_for_charts(day_pl_data)

        sorted_dates = sorted(days_formatted.keys())

        return jsonify({
            'success': True,
            'pressure_levels': PRESSURE_LEVELS,
            'days': days_formatted,
            'dates': sorted_dates
        })
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Fehler beim Laden der Höhenwind-Daten: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/email-config', methods=['GET'])
def api_email_config():
    """API-Endpoint zum Anzeigen der E-Mail-Konfiguration (ohne Passwort)."""
    if not EmailNotifier:
        return jsonify({
            'success': False,
            'error': 'E-Mail-Modul nicht verfügbar'
        }), 500
    
    try:
        # Lade .env neu, um aktuelle Werte zu bekommen
        try:
            from dotenv import load_dotenv
            load_dotenv(override=True)  # override=True überschreibt bestehende Werte
        except ImportError:
            pass
        
        notifier = EmailNotifier()
        config_status = notifier.check_configuration()
        
        # Zeige auch die aktuellen Umgebungsvariablen direkt
        current_sender = os.environ.get('EMAIL_SENDER')
        current_recipient = os.environ.get('EMAIL_RECIPIENT')
        
        # Zeige Konfiguration ohne Passwort
        safe_config = {
            'enabled': config_status['enabled'],
            'smtp_server': notifier.smtp_server,
            'smtp_port': notifier.smtp_port,
            'sender': notifier.sender,
            'sender_from_env': current_sender,  # Zeige auch direkt aus .env
            'recipient': notifier.recipient,
            'recipient_from_env': current_recipient,  # Zeige auch direkt aus .env
            'password_length': len(notifier.password) if notifier.password else 0,
            'password_has_spaces': ' ' in (notifier.password or ''),
            'missing_fields': config_status['missing_fields'],
            'errors': config_status['errors'],
            'note': 'Wenn Werte nicht übereinstimmen, starte den Server neu!'
        }
        
        return jsonify({
            'success': True,
            'config': safe_config
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/test-email', methods=['POST'])
def api_test_email():
    """API-Endpoint zum Testen der E-Mail-Benachrichtigung."""
    if not EmailNotifier:
        return jsonify({
            'success': False,
            'error': 'E-Mail-Modul nicht verfügbar'
        }), 500
    
    try:
        # Lade .env neu, um aktuelle Werte zu bekommen
        try:
            from dotenv import load_dotenv
            load_dotenv(override=True)  # override=True überschreibt bestehende Werte
        except ImportError:
            pass
        
        notifier = EmailNotifier()
        
        if not notifier.enabled:
            # Detaillierte Konfigurationsprüfung
            config_status = notifier.check_configuration()
            missing = ', '.join(config_status['missing_fields'])
            error_msg = f'E-Mail-Konfiguration nicht vollständig. Fehlende Felder: {missing}'
            if config_status['errors']:
                error_msg += f' Weitere Probleme: {"; ".join(config_status["errors"])}'
            return jsonify({
                'success': False,
                'error': error_msg,
                'config_status': config_status
            }), 400
        
        # Lade echte Evaluierungsdaten aus evaluations.json
        evaluations = get_evaluation_data()
        
        if not evaluations:
            return jsonify({
                'success': False,
                'error': 'Keine Evaluierungsdaten verfügbar. Bitte führe zuerst eine Analyse durch (python location_evaluator.py).'
            }), 404
        
        # Verwende die neueste Evaluierung (erste im Dictionary)
        # Sortiere nach Datum und nimm die neueste
        sorted_dates = sorted(evaluations.keys(), reverse=True)
        latest_date = sorted_dates[0]
        test_result = evaluations[latest_date]
        
        # Stelle sicher, dass alle benötigten Felder vorhanden sind
        if not test_result.get('conditions'):
            test_result['conditions'] = 'UNKNOWN'
        
        success, error_msg = notifier.send_alert(test_result, force_send=True)
        
        if success:
            return jsonify({
                'success': True,
                'message': f'Test-E-Mail erfolgreich gesendet an {notifier.recipient}'
            })
        else:
            # Detaillierte Fehlermeldung zurückgeben
            detailed_error = error_msg or 'E-Mail konnte nicht gesendet werden. Unbekannter Fehler.'
            
            # Häufige Probleme erkennen und hilfreiche Tipps geben
            if 'Authentifizierung' in detailed_error or 'Login' in detailed_error:
                detailed_error += ' Tipp: Stelle sicher, dass du ein Gmail App-Passwort verwendest (nicht dein normales Passwort).'
            elif 'Verbindung' in detailed_error or 'Connection' in detailed_error:
                detailed_error += ' Tipp: Prüfe ob EMAIL_SMTP_SERVER und EMAIL_SMTP_PORT korrekt sind.'
            elif 'TLS' in detailed_error:
                detailed_error += ' Tipp: Stelle sicher, dass Port 587 für TLS verwendet wird.'
            
            return jsonify({
                'success': False,
                'error': detailed_error
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Fehler beim Senden der Test-E-Mail: {str(e)}'
        }), 500

@app.route('/api/cron', methods=['GET', 'POST'])
def api_cron():
    """API-Endpoint für Cron-Job: Wetter abrufen + LLM-Analyse + Email."""
    import logging
    from datetime import datetime
    logger = logging.getLogger(__name__)
    
    results = {
        'success': False,
        'timestamp': datetime.now().isoformat(),
        'steps': {}
    }
    
    try:
        # Schritt 1: Wetterdaten abrufen
        logger.info("CRON: Starte Wetterdaten-Abruf...")
        if fetch_weather_for_location:
            weather_data = fetch_weather_for_location(save_to_file=True, output_path='/tmp/wetterdaten.json')
            if weather_data:
                results['steps']['weather'] = {'success': True, 'message': 'Wetterdaten abgerufen'}
                logger.info("CRON: Wetterdaten erfolgreich abgerufen")
            else:
                results['steps']['weather'] = {'success': False, 'message': 'Keine Daten'}
        else:
            results['steps']['weather'] = {'success': False, 'message': 'fetch_weather_for_location nicht verfügbar'}
        
        # Schritt 2: LLM-Analyse
        logger.info("CRON: Starte LLM-Analyse...")
        try:
            from location_evaluator import LocationEvaluator
            evaluator = LocationEvaluator(weather_json_path='/tmp/wetterdaten.json')
            analysis_results = evaluator.analyze()
            if analysis_results:
                results['steps']['llm'] = {'success': True, 'message': f'{len(analysis_results)} Tage analysiert'}
                logger.info(f"CRON: LLM-Analyse abgeschlossen für {len(analysis_results)} Tage")
            else:
                results['steps']['llm'] = {'success': False, 'message': 'Keine Ergebnisse'}
        except Exception as e:
            results['steps']['llm'] = {'success': False, 'message': str(e)}
            logger.error(f"CRON: LLM-Analyse fehlgeschlagen: {e}")
        
        # Schritt 3: E-Mail wurde bereits durch evaluator.analyze() gesendet
        results['steps']['email'] = {'success': True, 'message': 'E-Mail via analyze() gesendet'}
        
        results['success'] = all(step.get('success', False) for step in results['steps'].values())
        return jsonify(results)
        
    except Exception as e:
        logger.error(f"CRON: Fehler: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/trigger-update', methods=['POST'])
def api_trigger_update():
    """Manual trigger: Fetch weather, analyze, and send consolidated email."""
    import logging
    logger = logging.getLogger(__name__)
    try:
        from fetch_weather import fetch_weather_for_location
        from location_evaluator import LocationEvaluator
        
        results = {'steps': {}}
        
        # 1. Fetch
        weather_path = str(get_weather_json_path())
        weather_data = fetch_weather_for_location(save_to_file=True, output_path=weather_path)
        results['steps']['fetch'] = {'success': bool(weather_data)}
        
        # 2. In InstantDB speichern
        if weather_data and instantdb_save:
            try:
                db_success = instantdb_save(weather_data)
                results['steps']['instantdb'] = {'success': db_success}
                logger.info(f"InstantDB Speichern: {'OK' if db_success else 'FEHLER'}")
            except Exception as e:
                logger.error(f"InstantDB Speichern fehlgeschlagen: {e}")
                results['steps']['instantdb'] = {'success': False, 'error': str(e)}
        
        # 3. Cache invalidieren
        global CACHED_WEATHER_DATA, LAST_FETCH_TIME
        CACHED_WEATHER_DATA = None
        LAST_FETCH_TIME = 0
        
        # 4. Evaluate & Email (handled by evaluator)
        evaluator = LocationEvaluator(weather_json_path=weather_path)
        analysis_results = evaluator.analyze()
        results['steps']['evaluate'] = {'success': bool(analysis_results)}
        results['steps']['email'] = {'success': True, 'message': 'E-Mail wurde (falls konfiguriert) versendet'}
        
        # 5. Regionen-Daten aktualisieren (inkl. InstantDB-Speicherung)
        try:
            from fetch_regions import fetch_and_calculate_regions
            fetch_and_calculate_regions()
            results['steps']['regions'] = {'success': True}
            logger.info("Regionen-Daten erfolgreich aktualisiert")
        except Exception as e:
            logger.error(f"Regionen-Update fehlgeschlagen: {e}")
            results['steps']['regions'] = {'success': False, 'error': str(e)}

        # 6. Evaluierungen in InstantDB speichern
        if analysis_results and instantdb_save_eval:
            try:
                eval_file = get_evaluations_json_path()
                if eval_file and eval_file.exists():
                    with open(eval_file, 'r', encoding='utf-8') as f:
                        eval_data = json.load(f)
                    db_ok = instantdb_save_eval(eval_data)
                    results['steps']['instantdb_eval'] = {'success': db_ok}
                    logger.info(f"InstantDB Evaluierung-Speichern: {'OK' if db_ok else 'FEHLER'}")
            except Exception as e:
                logger.error(f"InstantDB Evaluierung-Speichern fehlgeschlagen: {e}")
                results['steps']['instantdb_eval'] = {'success': False, 'error': str(e)}
        
        results['success'] = True
        return jsonify(results)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/auto-email', methods=['GET', 'POST'])
def api_auto_email():
    """API-Endpoint für automatische E-Mail (ruft intern /api/cron auf)."""
    return api_cron()


if __name__ == '__main__':
    # Prüfe ob Wetterdaten vorhanden sind
    weather_file = Path("data/wetterdaten.json")
    if not weather_file.exists():
        print("[WARNUNG] data/wetterdaten.json nicht gefunden!")
        print("   Bitte zuerst 'python fetch_weather.py' ausführen.")
    
    print("=" * 60)
    print("Uetliberg Ticker - Web-Interface mit Zeitlinien-Diagrammen")
    print("=" * 60)
    print(f"\n[OK] Server startet auf http://localhost:5000")
    print(f"[INFO] Zeigt Wind, Niederschlag, Thermik und Wolkenbasis")
    print(f"[INFO] Inkludiert LLM-Auswertung")
    print(f"\n[TIP] Tipps:")
    print(f"   - Drücke Ctrl+C zum Beenden")
    print(f"   - Aktualisiere die Seite nach fetch_weather.py")
    print("=" * 60)
    print()
    
    app.run(debug=True, host='0.0.0.0', port=5000)

