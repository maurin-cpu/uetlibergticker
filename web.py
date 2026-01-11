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
        if isinstance(CACHED_WEATHER_DATA, dict):
            CACHED_WEATHER_DATA['_debug_source'] = "CACHE_MEMORY"
            CACHED_WEATHER_DATA['_debug_timestamp'] = str(LAST_FETCH_TIME)
        return CACHED_WEATHER_DATA
    
    # 2. Versuche Datei zu laden
    weather_file = None
    debug_source = "UNKNOWN"
    
    # Prüfe zuerst /tmp (für Vercel)
    if os.path.exists('/tmp'):
        tmp_path = Path('/tmp/wetterdaten.json')
        if tmp_path.exists():
            weather_file = tmp_path
            debug_source = "FILE_TMP"
    
    # Prüfe dann data/ (für lokale Entwicklung)
    if not weather_file:
        data_path = Path("data/wetterdaten.json")
        if data_path.exists():
            weather_file = data_path
            debug_source = "FILE_DATA"
            
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
                if isinstance(CACHED_WEATHER_DATA, dict):
                    CACHED_WEATHER_DATA['_debug_source'] = debug_source
                    CACHED_WEATHER_DATA['_debug_path'] = str(weather_file)
                LAST_FETCH_TIME = current_time
                return CACHED_WEATHER_DATA
                
        except Exception as e:
            logger.error(f"Fehler beim Lesen der Datei {weather_file}: {e}")
            # Fallback zu Live-Fetch bei defekter Datei
    

    
    # 3. Fallback: Live Abruf wenn keine Datei da ist oder sie fehlerhaft war
    logger.info("Keine lokalen Daten gefunden - Führe Live-Abruf durch...")
    
    if fetch_weather_for_location:
        try:
            # LIVE ABFRAGE: Speichere in /tmp/wetterdaten.json wenn möglich
            save_path = None
            save_allowed = False
            
            if os.path.exists('/tmp'): # Vercel
                save_path = '/tmp/wetterdaten.json'
                save_allowed = True
            
            if save_allowed and save_path:
                logger.info(f"Speichere Live-Daten temporär nach {save_path}")
                fresh_data = fetch_weather_for_location(save_to_file=True, output_path=save_path)
            else:
                logger.info("Kein passender Speicherpfad - nur im Speicher halten")
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
                    # Return tuple with debug info
                    if isinstance(CACHED_WEATHER_DATA, dict):
                        CACHED_WEATHER_DATA['_debug_source'] = "LIVE_FETCH"
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


def get_evaluation_data():
    """Lädt LLM-Auswertung aus evaluations.json oder generiert sie wenn nötig."""
    import logging
    logger = logging.getLogger(__name__)
    
    # Für Vercel: Verwende /tmp falls verfügbar, sonst data/
    evaluations_file = None
    
    # Prüfe zuerst /tmp (für Vercel)
    if os.path.exists('/tmp'):
        tmp_path = Path('/tmp/evaluations.json')
        if tmp_path.exists():
            evaluations_file = tmp_path
    
    # Prüfe dann data/ (für lokale Entwicklung)
    if not evaluations_file:
        data_path = Path("data/evaluations.json")
        if data_path.exists():
            evaluations_file = data_path
    
    # FALLBACK: Wenn keine Datei existiert, versuche ON-DEMAND zu generieren
    if not evaluations_file or not evaluations_file.exists():
        logger.warning("Keine Evaluierungsdatei gefunden - versuche On-Demand-Generierung...")
        
        try:
            # 1. Stelle sicher, dass Wetterdaten existieren (lädt sie in Cache & /tmp)
            load_weather_data()
            
            # 2. Prüfe ob Wetterdaten nun in /tmp liegen (durch load_weather_data erstellt)
            weather_path = None
            if os.path.exists('/tmp/wetterdaten.json'):
                weather_path = '/tmp/wetterdaten.json'
            elif Path("data/wetterdaten.json").exists():
                weather_path = "data/wetterdaten.json"
                
            if weather_path:
                from location_evaluator import LocationEvaluator
                logger.info(f"Starte Evaluator mit Wetterdaten aus {weather_path}")
                evaluator = LocationEvaluator(weather_json_path=weather_path)
                
                # Führe Analyse durch (speichert automatisch in /tmp/evaluations.json wenn möglich)
                results = evaluator.analyze()
                
                if results:
                    logger.info("On-Demand-Analyse erfolgreich!")
                    # Das Ergebnis ist eine Liste von Dictionaries, wir müssen es in das erwartete Format umwandeln
                    # group_by_json structure logic is duplicated here, better to reload file or construct dict
                    
                    # Versuche die neu erstellte Datei zu laden
                    if os.path.exists('/tmp/evaluations.json'):
                         evaluations_file = Path('/tmp/evaluations.json')
                    elif Path("data/evaluations.json").exists():
                         evaluations_file = Path("data/evaluations.json")
                         
        except Exception as e:
            logger.error(f"On-Demand-Generierung fehlgeschlagen: {e}")

    # Erneuter Check nach Generierungsversuch
    if not evaluations_file or not evaluations_file.exists():
        logger.warning("Konnte keine Evaluierungen laden oder generieren.")
        return {}
    
    try:
        logger.info(f"Lade Evaluierungen aus: {evaluations_file}")
        with open(evaluations_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Extrahiere Evaluierungen aus JSON-Struktur
        evaluations_list = data.get('evaluations', [])
        
        # Gruppiere nach Datum
        evaluations_by_date = {}
        for result in evaluations_list:
            date = result.get('date')
            if date:
                evaluations_by_date[date] = result
        
        return evaluations_by_date
        
    except Exception as e:
        logger.error(f"Fehler beim Laden der Evaluierungen: {e}")
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
        
        # Schritt 3: E-Mail senden
        logger.info("CRON: Sende E-Mail...")
        if EmailNotifier:
            try:
                notifier = EmailNotifier()
                if notifier.enabled:
                    evaluations = get_evaluation_data()
                    if evaluations:
                        sorted_dates = sorted(evaluations.keys(), reverse=True)
                        latest = evaluations[sorted_dates[0]]
                        success, error = notifier.send_alert(latest, force_send=True)
                        results['steps']['email'] = {'success': success, 'message': error or 'E-Mail gesendet'}
                    else:
                        results['steps']['email'] = {'success': False, 'message': 'Keine Evaluierungen'}
                else:
                    results['steps']['email'] = {'success': False, 'message': 'E-Mail deaktiviert'}
            except Exception as e:
                results['steps']['email'] = {'success': False, 'message': str(e)}
        else:
            results['steps']['email'] = {'success': False, 'message': 'EmailNotifier nicht verfügbar'}
        
        results['success'] = all(step.get('success', False) for step in results['steps'].values())
        return jsonify(results)
        
    except Exception as e:
        logger.error(f"CRON: Fehler: {e}")
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

