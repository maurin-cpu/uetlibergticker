#!/usr/bin/env python3
"""
Web-Interface Server für Uetliberg Ticker mit Zeitlinien-Diagrammen
Flask-basiertes Interface mit D3.js Visualisierung und LLM-Auswertung
"""

import json
import os
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template, jsonify, request
from config import FLIGHT_HOURS_START, FLIGHT_HOURS_END, LOCATION

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
    Lädt Wetterdaten.
    Reihenfolge:
    1. In-Memory Cache (weniger als 5 Min alt)
    2. JSON-Datei (/tmp oder data/)
    3. Live-Abruf (Fallback falls keine Datei)
    """
    global CACHED_WEATHER_DATA, LAST_FETCH_TIME
    import logging
    import time
    logger = logging.getLogger(__name__)
    
    current_time = time.time()
    
    # 1. Prüfe In-Memory Cache
    if CACHED_WEATHER_DATA and (current_time - LAST_FETCH_TIME < CACHE_DURATION):
        logger.info("Verwende gecachte Wetterdaten (In-Memory)")
        return CACHED_WEATHER_DATA
    
    # 2. Versuche Datei zu laden
    weather_file = None
    
    # Prüfe zuerst /tmp (für Vercel)
    if os.path.exists('/tmp'):
        tmp_path = Path('/tmp/wetterdaten.json')
        if tmp_path.exists():
            weather_file = tmp_path
    
    # Prüfe dann data/ (für lokale Entwicklung)
    if not weather_file:
        data_path = Path("data/wetterdaten.json")
        if data_path.exists():
            weather_file = data_path
            
    if weather_file and weather_file.exists():
        try:
            logger.info(f"Lade Wetterdaten aus: {weather_file}")
            with open(weather_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # Extrahiere Uetliberg Daten
            found_location = None
            for key in data.keys():
                if 'uetliberg' in key.lower() or 'balderen' in key.lower():
                    found_location = key
                    break
            
            if found_location:
                # Update Cache
                CACHED_WEATHER_DATA = data[found_location]
                LAST_FETCH_TIME = current_time
                return CACHED_WEATHER_DATA
                
        except Exception as e:
            logger.error(f"Fehler beim Lesen der Datei {weather_file}: {e}")
            # Fallback zu Live-Fetch bei defekter Datei
    
    # 3. Fallback: Live Abruf wenn keine Datei da ist oder sie fehlerhaft war
    logger.info("Keine lokalen Daten gefunden - Führe Live-Abruf durch...")
    
    if fetch_weather_for_location:
        try:
            # Live Abruf (nicht in Datei speichern, um Vercel Filesystem Probleme zu vermeiden)
            fresh_data = fetch_weather_for_location(save_to_file=False)
            
            if fresh_data:
                # Extrahiere Uetliberg Daten
                found_location = None
                for key in fresh_data.keys():
                    if 'uetliberg' in key.lower() or 'balderen' in key.lower():
                        found_location = key
                        break
                
                if found_location:
                    # Update Cache
                    CACHED_WEATHER_DATA = fresh_data[found_location]
                    LAST_FETCH_TIME = current_time
                    logger.info("Live-Daten erfolgreich abgerufen und gecacht")
                    return CACHED_WEATHER_DATA
        except Exception as e:
            logger.error(f"Live-Abruf fehlgeschlagen: {e}")
            
    # Wenn alles fehlschlägt
    error_msg = "Wetterdaten konnten weder aus Datei geladen noch live abgerufen werden."
    logger.error(error_msg)
    raise ValueError(error_msg)


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


def format_data_for_charts(hourly_data):
    """Formatiert Daten für D3.js Charts."""
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
            
            # Thermik-Daten (CAPE)
            cape = data.get('cape', 0)
            if cape is not None:
                chart_data['thermik'].append({
                    'time': time_str,
                    'cape': cape
                })
            
            # Wolkenbasis-Daten
            cloud_base = data.get('cloud_base')
            if cloud_base is not None:
                chart_data['cloudbase'].append({
                    'time': time_str,
                    'height': cloud_base
                })
        except Exception:
            continue
    
    return chart_data


def get_evaluation_data():
    """Lädt LLM-Auswertung aus evaluations.json."""
    import logging
    logger = logging.getLogger(__name__)
    
    # Für Vercel: Verwende /tmp falls verfügbar, sonst data/
    evaluations_file = None
    checked_paths = []
    
    # Prüfe zuerst /tmp (für Vercel)
    if os.path.exists('/tmp'):
        tmp_path = Path('/tmp/evaluations.json')
        checked_paths.append(str(tmp_path))
        if tmp_path.exists():
            evaluations_file = tmp_path
            logger.info(f"Evaluierungen gefunden in: {tmp_path}")
    
    # Prüfe dann data/ (für lokale Entwicklung)
    if not evaluations_file:
        data_path = Path("data/evaluations.json")
        checked_paths.append(str(data_path))
        if data_path.exists():
            evaluations_file = data_path
            logger.info(f"Evaluierungen gefunden in: {data_path}")
    
    if not evaluations_file or not evaluations_file.exists():
        error_msg = (
            f"WARNUNG: evaluations.json nicht gefunden. "
            f"Geprüfte Pfade: {', '.join(checked_paths)}. "
            f"Dies ist normal, wenn der Cron-Job noch nicht gelaufen ist. "
            f"Rufe /api/cron auf, um Daten zu generieren."
        )
        logger.warning(error_msg)
        print(error_msg)
        return {}
    
    try:
        logger.info(f"Lade Evaluierungen aus: {evaluations_file}")
        with open(evaluations_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Extrahiere Evaluierungen aus JSON-Struktur
        evaluations_list = data.get('evaluations', [])
        
        if not evaluations_list:
            error_msg = (
                f"WARNUNG: Keine Evaluierungen in evaluations.json gefunden. "
                f"Die Datei existiert, ist aber leer oder enthält keine 'evaluations' Liste. "
                f"Rufe /api/cron auf, um neue Evaluierungen zu generieren."
            )
            logger.warning(error_msg)
            print(error_msg)
            return {}
        
        # Gruppiere nach Datum
        evaluations_by_date = {}
        for result in evaluations_list:
            date = result.get('date')
            if date:
                evaluations_by_date[date] = result
        
        logger.info(f"Erfolgreich {len(evaluations_by_date)} Evaluierungen geladen")
        return evaluations_by_date
        
    except json.JSONDecodeError as e:
        error_msg = (
            f"FEHLER: evaluations.json ist kein gültiges JSON. "
            f"Datei: {evaluations_file}, Fehler: {str(e)}. "
            f"Die Datei könnte beschädigt sein. Rufe /api/cron auf, um sie neu zu generieren."
        )
        logger.error(error_msg, exc_info=True)
        print(error_msg)
        return {}
    except PermissionError as e:
        error_msg = (
            f"FEHLER: Keine Berechtigung zum Lesen von evaluations.json. "
            f"Datei: {evaluations_file}, Fehler: {str(e)}"
        )
        logger.error(error_msg, exc_info=True)
        print(error_msg)
        return {}
    except Exception as e:
        error_msg = (
            f"FEHLER: Unerwarteter Fehler beim Laden der Evaluierungen. "
            f"Datei: {evaluations_file}, Fehler: {str(e)}"
        )
        logger.error(error_msg, exc_info=True)
        print(error_msg)
        return {}


@app.route('/')
def index():
    """Hauptroute für das Web-Interface."""
    return render_template('weather_timeline.html')


@app.route('/api/weather')
def api_weather():
    """API-Endpoint für Wetterdaten."""
    try:
        weather_data = load_weather_data()
        hourly_data = weather_data.get('hourly_data', {})
        flight_hours_data = filter_flight_hours(hourly_data)
        
        # Gruppiere nach Tagen
        days_data = group_by_days(flight_hours_data)
        
        # Formatiere Daten für jeden Tag
        days_formatted = {}
        for date_key, day_hourly_data in days_data.items():
            days_formatted[date_key] = format_data_for_charts(day_hourly_data)
        
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
            'total_hours': len(flight_hours_data)
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
        # Lade die rohen JSON-Daten direkt
        # Für Vercel: Verwende /tmp falls verfügbar, sonst data/
        weather_file = None
        if os.path.exists('/tmp') and Path('/tmp/wetterdaten.json').exists():
            weather_file = Path('/tmp/wetterdaten.json')
        elif Path("data/wetterdaten.json").exists():
            weather_file = Path("data/wetterdaten.json")
        
        if not weather_file or not weather_file.exists():
            return jsonify({
                'error': 'Wetterdaten nicht gefunden. Bitte warten Sie, bis der Cron-Job die Daten erstellt hat.'
            }), 404
        
        with open(weather_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
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
        evaluations_file = None
        if os.path.exists('/tmp') and Path('/tmp/evaluations.json').exists():
            evaluations_file = Path('/tmp/evaluations.json')
        elif Path("data/evaluations.json").exists():
            evaluations_file = Path("data/evaluations.json")
        
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

