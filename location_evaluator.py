"""
Location Evaluator - Data Provider für LLM-basierte Gleitschirm Flugbarkeits-Evaluierung

Bereitet Wetterdaten für den Uetliberg Startplatz auf und stellt sie einem LLM zur Verfügung.
Die GESAMTE Flugbarkeits-Analyse wird vom LLM durchgeführt.
"""

import os
import json
import requests
import logging
import time
from typing import Dict, List, Tuple
from datetime import datetime
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from thermik_calculator import analyze_hour, calculate_thermal_profile, calculate_dewpoint

from config import (
    LLM_SYSTEM_PROMPT,
    LLM_USER_PROMPT_TEMPLATE,
    LOCATION,
    FORECAST_DAYS,
    FLIGHT_HOURS_START,
    FLIGHT_HOURS_END,
    PRESSURE_LEVELS,
    get_weather_json_path,
    get_evaluations_json_path
)

try:
    from email_notifier import EmailNotifier
except ImportError:
    EmailNotifier = None

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    ORANGE = '\033[38;5;208m'
    RED = '\033[91m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


class LocationEvaluator:
    """Evaluiert Flugbarkeit des Uetliberg Startplatzes basierend auf Wetterdaten."""
    
    def __init__(self, weather_json_path: str = None, model: str = None):
        self.weather_json_path = weather_json_path or str(get_weather_json_path())
        self.model = model or os.environ.get('OPENAI_MODEL', 'gpt-4.1-mini')
        self.api_key = os.environ.get('OPENAI_API_KEY')
        
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY nicht gesetzt")
        
        # Initialisiere E-Mail-Notifier (optional)
        if EmailNotifier:
            try:
                self.email_notifier = EmailNotifier()
            except Exception as e:
                logger.warning(f"E-Mail-Notifier konnte nicht initialisiert werden: {e}")
                self.email_notifier = None
        else:
            self.email_notifier = None
    
    def analyze(self) -> List[Dict]:
        """Hauptmethode: Lädt Wetterdaten und erstellt Ticker für jeden Forecast-Tag."""
        logger.info(f"Analysiere Uetliberg Startplatz für {FORECAST_DAYS} Tage")
        
        # Lade Wetterdaten für Uetliberg
        weather_data = self._load_weather_data()
        hourly_data = weather_data.get('hourly_data', {})
        pressure_level_data = weather_data.get('pressure_level_data', {})

        # Gruppiere nach Tagen und filtere Flugstunden
        days_data = self._group_by_days(hourly_data, pressure_level_data)
        
        # Sortiere Tage chronologisch und limitiere auf FORECAST_DAYS
        sorted_dates = sorted(days_data.keys())[:FORECAST_DAYS]
        
        results = []
        for date in sorted_dates:
            day_data = days_data[date]
            logger.info(f"Analysiere Tag: {date} ({len(day_data)} Stunden)")
            result = self.analyze_day(day_data, date)
            results.append(result)
        
        # Speichere Ergebnisse in JSON-Datei
        if results:
            try:
                self._save_evaluations_to_json(results)
            except Exception as e:
                logger.warning(f"Fehler beim Speichern der Evaluierungen: {e}")
            
            # E-Mail-Benachrichtigung an alle Subscriber (inkl. fester Empfänger) senden
            if self.email_notifier:
                try:
                    success, error_msg = self.email_notifier.send_multi_day_to_all_subscribers(results, force_send=True)
                    if not success and error_msg:
                        logger.warning(f"E-Mail-Benachrichtigung fehlgeschlagen: {error_msg}")
                    else:
                        logger.info(f"Konsolidierte E-Mail an alle Subscriber gesendet")
                except Exception as e:
                    logger.warning(f"Fehler beim Senden der konsolidierten E-Mail: {e}")
        
        return results
    
    def analyze_day(self, day_data: Dict, date: str) -> Dict:
        """Analysiert einen einzelnen Tag."""
        # Extrahiere Pressure-Level-Daten (spezieller Key)
        pressure_level_data = day_data.pop('_pressure_levels', {})

        # Kombiniere mit Standort-Info aus config.py
        location_data = {
            'name': LOCATION['name'],
            'fluggebiet': LOCATION['fluggebiet'],
            'typ': LOCATION['typ'],
            'windrichtung': LOCATION['windrichtung'],
            'bemerkung': LOCATION['bemerkung'],
            'hourly_data': day_data,
            'pressure_level_data': pressure_level_data,
            'date': date
        }

        # LLM-Analyse durchführen
        try:
            result = self._analyze_with_llm(location_data)
            result['location'] = LOCATION['name']
            result['date'] = date
            result['timestamp'] = datetime.now().isoformat()
            
            return result
        except Exception as e:
            logger.error(f"Fehler bei LLM-Analyse für {date}: {e}")
            return {
                "flyable": False,
                "rating": 0,
                "day_summary": f"Fehler: {str(e)}",
                "golden_window": None,
                "details": {"wind": "", "thermik": "", "risks": f"Systemfehler: {str(e)}"},
                "recommendation": "Bitte später erneut versuchen.",
                "sectors": [],
                "timestamp": datetime.now().isoformat(),
                "location": LOCATION['name'],
                "date": date
            }
    
    def _filter_flight_hours(self, hourly_data: Dict, start_hour: int, end_hour: int) -> Dict:
        """Filtert Stunden-Daten auf Flugstunden (start_hour <= Stunde < end_hour)."""
        filtered = {}
        for timestamp, data in hourly_data.items():
            try:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                hour = dt.hour
                if start_hour <= hour < end_hour:
                    filtered[timestamp] = data
            except Exception as e:
                logger.warning(f"Fehler beim Parsen von {timestamp}: {e}")
                continue
        return filtered
    
    def _group_by_days(self, hourly_data: Dict, pressure_level_data: Dict = None) -> Dict[str, Dict]:
        """Gruppiert Stunden-Daten nach Tagen und filtert auf Flugstunden."""
        if pressure_level_data is None:
            pressure_level_data = {}

        # Gruppiere zuerst nach Tagen
        days_data = {}
        for timestamp, data in hourly_data.items():
            try:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                date_key = dt.strftime("%Y-%m-%d")
                if date_key not in days_data:
                    days_data[date_key] = {}
                days_data[date_key][timestamp] = data
            except Exception as e:
                logger.warning(f"Fehler beim Gruppieren von {timestamp}: {e}")
                continue

        # Gruppiere Pressure-Level-Daten nach Tagen
        days_pl_data = {}
        for timestamp, pl_data in pressure_level_data.items():
            try:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                date_key = dt.strftime("%Y-%m-%d")
                if date_key not in days_pl_data:
                    days_pl_data[date_key] = {}
                days_pl_data[date_key][timestamp] = pl_data
            except Exception:
                continue

        # Filtere dann innerhalb jedes Tages auf Flugstunden
        filtered_days_data = {}
        for date_key, day_hourly_data in days_data.items():
            flight_hours_data = self._filter_flight_hours(day_hourly_data, FLIGHT_HOURS_START, FLIGHT_HOURS_END)
            # Pressure-Level-Daten für diesen Tag anhängen (als spezieller Key)
            flight_hours_data['_pressure_levels'] = days_pl_data.get(date_key, {})
            filtered_days_data[date_key] = flight_hours_data

        return filtered_days_data
    
    def _load_weather_data(self) -> Dict:
        """Lädt Wetterdaten für Uetliberg aus JSON-Datei."""
        path = Path(self.weather_json_path)
        if not path.exists():
            raise FileNotFoundError(f"Wetterdaten nicht gefunden: {self.weather_json_path}")
        
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Suche Uetliberg Eintrag
        for key in data.keys():
            if 'uetliberg' in key.lower() or 'balderen' in key.lower():
                return data[key]
        
        raise ValueError(f"Keine Wetterdaten für Uetliberg gefunden")
    
    def _format_hourly_data(self, hourly_data: Dict, pressure_level_data: Dict = None, hours: int = 6) -> str:
        """Formatiert stündliche Daten für Prompt inkl. Thermik-Berechnungen (nur Flugstunden)."""
        if not hourly_data:
            return "Keine stündlichen Daten verfügbar"
        
        if pressure_level_data is None:
            pressure_level_data = {}
            
        sorted_times = sorted(hourly_data.keys())
        lines = []
        count = 0
        
        for timestamp in sorted_times:
            # Filtere auf Flugstunden
            try:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                if not (FLIGHT_HOURS_START <= dt.hour < FLIGHT_HOURS_END):
                    continue
            except Exception:
                continue
                
            if count >= hours:
                break
            count += 1
            
            data = hourly_data[timestamp]
            time_str = timestamp.replace('T', ' ')[:16]
            
            temp = data.get('temperature_2m', 'N/A')
            wind_speed = data.get('wind_speed_10m', 'N/A')
            wind_dir = data.get('wind_direction_10m', 'N/A')
            wind_gusts = data.get('wind_gusts_10m', 'N/A')
            cloud_base_raw = data.get('cloud_base')
            cloud_base = f"{cloud_base_raw}m" if cloud_base_raw is not None else 'wolkenfrei'
            cloud_cover = data.get('cloud_cover', 'N/A')
            cape = data.get('cape', 'N/A')
            precip = data.get('precipitation', 'N/A')
            sunshine = data.get('sunshine_duration', 'N/A')

            if isinstance(sunshine, (int, float)) and sunshine > 0:
                sunshine_str = f"{sunshine / 3600:.1f}h"
            else:
                sunshine_str = "0h"

            # Neues Top-Modell für Thermikberechnung nutzen
            thermal_info = ""
            try:
                p_levels = []
                for level in [1000, 975, 950, 925, 900, 875, 850, 825, 800, 775, 750, 700, 600]:
                    h_val = pressure_level_data.get(timestamp, {}).get(f'geopotential_height_{level}hPa')
                    t_val = pressure_level_data.get(timestamp, {}).get(f'temperature_{level}hPa')
                    if h_val is not None and t_val is not None:
                        p_levels.append({'pressure': level, 'height': h_val, 'temp': t_val})

                from thermik_calculator import calculate_thermal_profile, calculate_dewpoint
                surf_dew = calculate_dewpoint(data.get('temperature_2m'), data.get('relative_humidity_2m', 50))

                therm = calculate_thermal_profile(
                    surface_temp=data.get('temperature_2m'),
                    surface_dewpoint=surf_dew,
                    elevation_m=LOCATION.get('elevation_ref', 850.0),
                    pressure_levels_data=p_levels,
                    boundary_layer_height_agl=data.get('boundary_layer_height'),
                    sunshine_duration_s=data.get('sunshine_duration'),
                    surface_sensible_heat_flux=data.get('surface_sensible_heat_flux'),
                    surface_latent_heat_flux=data.get('surface_latent_heat_flux'),
                    shortwave_radiation=data.get('shortwave_radiation'),
                    direct_radiation=data.get('direct_radiation'),
                    diffuse_radiation=data.get('diffuse_radiation'),
                    soil_moisture=data.get('soil_moisture_0_to_1cm'),
                    soil_temperature=data.get('soil_temperature_0cm'),
                    updraft=data.get('updraft'),
                    et0=data.get('et0_fao_evapotranspiration'),
                    vpd=data.get('vapour_pressure_deficit'),
                    lifted_index=data.get('lifted_index'),
                    convective_inhibition=data.get('convective_inhibition'),
                    snow_depth=data.get('snow_depth'),
                    timestamp=timestamp,
                    slope_azimuth=LOCATION.get('slope_azimuth'),
                    slope_angle=LOCATION.get('slope_angle'),
                )

                if 'error' not in therm:
                    climb = therm['climb_rate']
                    max_h = therm['max_height']
                    lcl = therm.get('lcl')
                    lcl_str = f", LCL/Basis {lcl}m" if lcl else ""
                    thermal_info = f" | THERMIK-PROXY: {climb} m/s bis {max_h}m MSL{lcl_str} (Güte: {therm['rating']}/10)"
            except Exception as e:
                import traceback
                err_str = traceback.format_exc().split('\n')[-2]
                thermal_info = f" | Thermik-Fehler: {e} ({err_str})"

            line = (
                f"{time_str}: Temp {temp}°C | "
                f"Wind {wind_speed}km/h aus {wind_dir}° (Böen {wind_gusts}km/h) | "
                f"Wolkenbasis {cloud_base} | Bewölkung {cloud_cover}% | "
                f"CAPE {cape} J/kg | Niederschlag {precip}mm | Sonne {sunshine_str}"
                f"{thermal_info}"
            )
            lines.append(line)
        
        return "\n".join(lines)
    
    def _format_altitude_wind_profile(self, pressure_level_data: Dict, hours: int = 6) -> str:
        """Formatiert Höhenwind-Daten für LLM-Prompt (nur Flugstunden, reduzierte Level)."""
        if not pressure_level_data:
            return "Keine Höhenwind-Daten verfügbar"

        sorted_times = sorted(pressure_level_data.keys())
        lines = []
        count = 0

        # Sende nur 3 kritische Level, um Tokens zu sparen (Boden/Inversion, mittlere Höhe, Scherungs-Höhe)
        # 850hPa (~1500m), 700hPa (~3000m), 500hPa (~5500m)
        REDUCED_LEVELS = [850, 700, 500]

        for timestamp in sorted_times:
            # Filtere auf Flugstunden
            try:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                if not (FLIGHT_HOURS_START <= dt.hour < FLIGHT_HOURS_END):
                    continue
            except Exception:
                continue

            if count >= hours:
                break
            count += 1

            data = pressure_level_data[timestamp]
            time_str = timestamp.replace('T', ' ')[:16]

            altitude_data = []
            for level in REDUCED_LEVELS:
                height = data.get(f'geopotential_height_{level}hPa')
                wind_speed = data.get(f'wind_speed_{level}hPa')
                wind_dir = data.get(f'wind_direction_{level}hPa')
                temp = data.get(f'temperature_{level}hPa')

                if height is not None and wind_speed is not None and isinstance(height, (int, float)):
                    dir_str = f" aus {wind_dir:.0f}°" if wind_dir is not None else ""
                    temp_str = f", Temp {temp:.1f}°C" if temp is not None else ""
                    altitude_data.append(
                        f"  {int(height)}m MSL ({level}hPa): Wind {wind_speed:.1f}km/h{dir_str}{temp_str}"
                    )

            if altitude_data:
                lines.append(f"\n{time_str}:")
                lines.extend(altitude_data)

        return "\n".join(lines) if lines else "Keine Höhenwind-Daten verfügbar"

    def _build_prompt(self, location_data: Dict) -> Tuple[str, str]:
        """Erstellt System- und User-Prompt."""
        bemerkungen = location_data.get('bemerkung', '')
        bemerkungen_list = [b.strip() for b in bemerkungen.split('|') if b.strip()] if bemerkungen else []

        hourly_data = location_data.get('hourly_data', {})
        pressure_level_data = location_data.get('pressure_level_data', {})
        date = location_data.get('date', '')

        # Ermittle Anzahl der echten Flugstunden in den Daten um hours-Limit richtig zu setzen
        total_flight_hours = 0
        for ts in hourly_data.keys():
            try:
                if FLIGHT_HOURS_START <= datetime.fromisoformat(ts.replace('Z', '+00:00')).hour < FLIGHT_HOURS_END:
                    total_flight_hours += 1
            except: pass

        # Formatiere alle verfügbaren Flugstunden
        formatted_hours = self._format_hourly_data(hourly_data, pressure_level_data, hours=total_flight_hours)

        # Formatiere Höhenwind-Daten (auch hier nur Flugstunden, z.B. die ersten 10)
        formatted_altitude_wind = self._format_altitude_wind_profile(pressure_level_data, hours=10)

        # Föhn-Indikator-Daten laden und formatieren
        foehn_info = ""
        try:
            from foehn_indicators import get_foehn_for_dashboard
            foehn_result = get_foehn_for_dashboard(forecast_days=2)
            if foehn_result.get('success') and foehn_result.get('foehn'):
                f = foehn_result['foehn']
                foehn_lines = ["\nFÖHN-INDIKATOR (Süd→Nord, Lugano→Zürich):"]
                foehn_lines.append(f"  Level: {f.get('level', 'none').upper()}")
                if f.get('delta_p_hpa') is not None:
                    foehn_lines.append(f"  Delta-P (Süd-Nord): {f['delta_p_hpa']} hPa")
                if f.get('crest_wind_kmh') is not None:
                    dir_str = f" aus {f['crest_dir_deg']}°" if f.get('crest_dir_deg') is not None else ""
                    foehn_lines.append(f"  Kammwind 700hPa: {f['crest_wind_kmh']} km/h{dir_str}")
                if f.get('humidity_nord') is not None:
                    foehn_lines.append(f"  Luftfeuchtigkeit Nordseite: {f['humidity_nord']}%")
                if f.get('gust_ratio') is not None:
                    foehn_lines.append(f"  Böigkeit-Ratio: {f['gust_ratio']}")
                indicators = f.get('indicators', [])
                if indicators:
                    foehn_lines.append(f"  Indikatoren: {'; '.join(indicators)}")
                foehn_info = "\n".join(foehn_lines) + "\n"
                logger.info(f"Föhn-Daten in Prompt eingefügt: Level={f.get('level')}")
        except Exception as e:
            logger.warning(f"Föhn-Daten konnten nicht geladen werden: {e}")
            foehn_info = ""

        # Höhenwind-Sektion (nur wenn Daten vorhanden)
        altitude_wind_section = ""
        if formatted_altitude_wind != "Keine Höhenwind-Daten verfügbar":
            altitude_wind_section = f"\n\n═══════════════════════════════════════\nHÖHENWIND-PROFIL:\n═══════════════════════════════════════\n{formatted_altitude_wind}"

        # Flugstunden-Info
        flight_hours_info = f"\n\nWICHTIG: Diese Analyse bezieht sich nur auf Flugstunden ({FLIGHT_HOURS_START:02d}:00-{FLIGHT_HOURS_END:02d}:00) für {date}."

        user_prompt = LLM_USER_PROMPT_TEMPLATE.format(
            name=location_data.get('name', 'N/A'),
            fluggebiet=location_data.get('fluggebiet', 'N/A'),
            typ=location_data.get('typ', 'N/A'),
            windrichtung=location_data.get('windrichtung', 'Nicht angegeben'),
            besonderheiten=', '.join(bemerkungen_list) if bemerkungen_list else 'Keine',
            hourly_data=formatted_hours,
            foehn_info=foehn_info,
            total_hours=total_flight_hours,
            flight_hours_start=FLIGHT_HOURS_START,
            flight_hours_end=FLIGHT_HOURS_END
        ) + flight_hours_info + altitude_wind_section

        return LLM_SYSTEM_PROMPT, user_prompt
    
    def _analyze_with_llm(self, location_data: Dict) -> Dict:
        """Sendet aufbereitete Daten an OpenAI GPT."""
        # Prüfe API-Key
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY nicht gesetzt")
        
        if not self.api_key.startswith('sk-'):
            logger.warning(f"API-Key scheint ungültig zu sein (sollte mit 'sk-' beginnen)")
        
        system_prompt, user_prompt = self._build_prompt(location_data)
        
        url = "https://api.openai.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        
        json_supported_models = ["gpt-4-turbo", "gpt-4-turbo-preview", "gpt-4-0125-preview", "gpt-4o", "gpt-4o-mini", "gpt-4.1-mini", "gpt-4.1-nano", "gpt-3.5-turbo"]
        
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            "temperature": 0.3
        }
        
        if any(model in self.model for model in json_supported_models):
            payload["response_format"] = {"type": "json_object"}
        
        logger.info(f"OpenAI API Call: Model={self.model}, Prompt-Länge: System={len(system_prompt)}, User={len(user_prompt)}")
        
        max_retries = 3
        retry_delay = 1
        last_error = None
        
        for attempt in range(max_retries):
            try:
                logger.debug(f"API Call Versuch {attempt + 1}/{max_retries}")
                response = requests.post(url, headers=headers, json=payload, timeout=60)
                
                if response.status_code == 200:
                    logger.info("OpenAI API Call erfolgreich")
                    return self._parse_llm_response(response.json())
                elif response.status_code == 429:
                    wait_time = retry_delay * (2 ** attempt) * 2
                    logger.warning(f"Rate limit (429), warte {wait_time}s vor Retry {attempt + 1}/{max_retries}")
                    time.sleep(wait_time)
                    continue
                elif response.status_code == 401:
                    error_msg = f"API Authentifizierungsfehler (401): Ungültiger API-Key? Response: {response.text[:200]}"
                    logger.error(error_msg)
                    raise Exception(error_msg)
                else:
                    error_text = response.text[:500] if response.text else "Keine Fehlermeldung"
                    last_error = f"API Fehler {response.status_code}: {error_text}"
                    logger.warning(f"{last_error} (Versuch {attempt + 1}/{max_retries})")
                    if attempt == max_retries - 1:
                        raise Exception(last_error)
                    time.sleep(retry_delay * (2 ** attempt))
            except requests.Timeout:
                last_error = "OpenAI API Timeout nach 60 Sekunden"
                logger.warning(f"{last_error} (Versuch {attempt + 1}/{max_retries})")
                if attempt == max_retries - 1:
                    raise Exception(last_error)
                time.sleep(retry_delay * (2 ** attempt))
            except requests.RequestException as e:
                last_error = f"API Request-Fehler: {str(e)}"
                logger.warning(f"{last_error} (Versuch {attempt + 1}/{max_retries})")
                if attempt == max_retries - 1:
                    raise Exception(last_error)
                time.sleep(retry_delay * (2 ** attempt))
            except Exception as e:
                # Andere Exceptions (z.B. 401) direkt weiterwerfen
                raise
        
        # Sollte eigentlich nie erreicht werden, aber als Fallback
        raise Exception(f"OpenAI API Call fehlgeschlagen nach {max_retries} Versuchen. Letzter Fehler: {last_error}")
    
    def _parse_llm_response(self, response_json: Dict) -> Dict:
        """Extrahiert und validiert JSON aus LLM-Antwort."""
        content = response_json['choices'][0]['message']['content']
        result = json.loads(content)
        
        # Validiere kritische Felder, aber behalte alle Details vollständig
        if 'flyable' not in result:
            result['flyable'] = False
        if 'details' not in result or not isinstance(result['details'], dict):
            result['details'] = {}
        
        # Stelle sicher, dass Details-Felder existieren (aber nicht überschreiben wenn vorhanden)
        if 'wind' not in result.get('details', {}):
            result.setdefault('details', {})['wind'] = "Nicht verfügbar"
        if 'thermik' not in result.get('details', {}):
            result.setdefault('details', {})['thermik'] = "Nicht verfügbar"
        if 'risks' not in result.get('details', {}):
            result.setdefault('details', {})['risks'] = "Nicht verfügbar"
        
        result['flyable'] = bool(result.get('flyable', False))
        result['rating'] = int(result.get('rating', 0))
        
        # day_summary → summary Mapping (Abwärtskompatibilität mit Frontend)
        if 'day_summary' in result:
            result['summary'] = result['day_summary']
        elif 'summary' not in result:
            result['summary'] = "Keine Zusammenfassung verfügbar"
        
        # golden_window extrahieren
        if 'golden_window' not in result:
            result['golden_window'] = None
        
        if 'recommendation' not in result:
            result['recommendation'] = "Keine Empfehlung verfügbar"
        
        # Parse und validiere Sektoren (neues Format, ersetzt hourly_evaluations)
        if 'sectors' in result and isinstance(result['sectors'], list):
            validated_sectors = []
            for sector in result['sectors']:
                if isinstance(sector, dict):
                    validated = {
                        'slot': str(sector.get('slot', '')),
                        'safety': str(sector.get('safety', 'SAFE')).upper(),
                        'flyable': bool(sector.get('flyable', False)),
                        'rating': int(sector.get('rating', 0)),
                        'wind_info': str(sector.get('wind_info', '')),
                        'reason': str(sector.get('reason', 'Keine Begründung'))
                    }
                    validated_sectors.append(validated)
            result['sectors'] = validated_sectors
        else:
            result['sectors'] = []
        
        # Conditions aus Sektoren ableiten (5 Stufen)
        if 'conditions' not in result:
            if result['sectors']:
                result['conditions'] = self._derive_day_conditions(result['sectors'], result.get('rating', 0))
            else:
                result['conditions'] = 'UNKNOWN'
        
        # hourly_evaluations Kompatibilität: Aus Sektoren generieren
        result['hourly_evaluations'] = self._sectors_to_hourly(result.get('sectors', []))
        
        return result
    
    @staticmethod
    def _sector_to_condition(safety: str, flyable: bool, rating: int) -> str:
        """
        Mappt einen Sektor auf eine der 5 Flugkategorien basierend auf Flughöhe:

        LEGENDARY  - Streckenflug, riesige Höhe über Startplatz (rating >= 9)
        GOOD       - Soaring/Thermik am Hang, mittlere Höhe über Start (rating >= 7)
        FLYABLE    - Abgleiter, safe aber wenig Höhe (rating < 7)
        CAUTION    - Grenzwertige Bedingungen (safety=CAUTION)
        DANGEROUS  - Sicherheitsrisiko (safety=DANGEROUS)
        """
        # Sicherheits-Zustände (Top-Priorität)
        if safety == 'DANGEROUS':
            return 'DANGEROUS'
        if safety == 'CAUTION':
            return 'CAUTION'
            
        # Qualitäts-Zustände (Wenn safety SAFE ist)
        if rating >= 9:
            return 'LEGENDARY'
        if rating >= 7:
            return 'GOOD'
        return 'FLYABLE'

    def _derive_day_conditions(self, sectors: List[Dict], day_rating: int) -> str:
        """Leitet die Tages-Condition aus allen Sektoren ab."""
        if not sectors:
            return 'UNKNOWN'

        # Beste Condition des Tages (für den Hero-Banner)
        order = {'DANGEROUS': 0, 'CAUTION': 1, 'FLYABLE': 2, 'GOOD': 3, 'LEGENDARY': 4}
        best = 'DANGEROUS'
        for s in sectors:
            cond = self._sector_to_condition(
                s.get('safety', 'SAFE'), s.get('flyable', False), s.get('rating', 0)
            )
            if order.get(cond, 0) > order.get(best, 0):
                best = cond
        return best

    def _sectors_to_hourly(self, sectors: List[Dict]) -> List[Dict]:
        """Konvertiert Sektoren in hourly_evaluations für Frontend-Kompatibilität."""
        hourly = []

        for sector in sectors:
            slot = sector.get('slot', '')
            if '-' not in slot:
                continue
            try:
                start_str, end_str = slot.split('-')
                start_hour = int(start_str.split(':')[0])
                end_hour = int(end_str.split(':')[0])

                condition = self._sector_to_condition(
                    sector.get('safety', 'SAFE'),
                    sector.get('flyable', False),
                    sector.get('rating', 0)
                )

                for h in range(start_hour, end_hour):
                    if FLIGHT_HOURS_START <= h < FLIGHT_HOURS_END:
                        hourly.append({
                            'hour': h,
                            'timestamp': '',
                            'conditions': condition,
                            'flyable': sector.get('flyable', False),
                            'rating': sector.get('rating', 0),
                            'reason': sector.get('reason', '')
                        })
            except (ValueError, IndexError):
                continue

        return hourly
    
    def format_terminal_output(self, result: Dict, use_colors: bool = True) -> str:
        """Formatiert das Evaluierungs-Ergebnis für Terminal-Ausgabe."""
        def color(text: str, color_code: str) -> str:
            return f"{color_code}{text}{Colors.RESET}" if use_colors else text
        
        def bold(text: str) -> str:
            return f"{Colors.BOLD}{text}{Colors.RESET}" if use_colors else text
        
        conditions = result.get('conditions', 'UNKNOWN').upper()
        condition_labels = {
            'LEGENDARY': 'LEGENDÄR', 'GOOD': 'GUT', 'FLYABLE': 'FLIEGBAR',
            'CAUTION': 'AUFPASSEN', 'DANGEROUS': 'GEFÄHRLICH'
        }
        if conditions == 'LEGENDARY':
            condition_color = '\033[95m'  # Magenta/Purple
            condition_icon = '🏆'
        elif conditions == 'GOOD':
            condition_color = Colors.GREEN
            condition_icon = '✅'
        elif conditions == 'FLYABLE':
            condition_color = Colors.CYAN
            condition_icon = '🪂'
        elif conditions == 'CAUTION':
            condition_color = Colors.YELLOW
            condition_icon = '⚠️'
        elif conditions == 'DANGEROUS':
            condition_color = Colors.RED
            condition_icon = '🚫'
        else:
            condition_color = Colors.YELLOW
            condition_icon = '❓'
        conditions = condition_labels.get(conditions, conditions)
        
        flyable = result.get('flyable', False)
        flyable_text = color("FLUGBAR", Colors.GREEN) if flyable else color("NICHT FLUGBAR", Colors.RED)
        conditions_text = color(conditions, condition_color)
        
        rating = result.get('rating', 0)
        confidence = result.get('confidence', 0)
        rating_stars = '⭐' * min(rating, 10)
        rating_bar = '█' * confidence + '░' * (10 - confidence)
        
        timestamp = result.get('timestamp', '')
        try:
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            timestamp_str = dt.strftime('%Y-%m-%d %H:%M:%S')
        except:
            timestamp_str = timestamp
        
        location = result.get('location', 'Unbekannt')
        date = result.get('date', '')
        summary = result.get('summary', 'Keine Zusammenfassung verfügbar')
        details = result.get('details', {})
        recommendation = result.get('recommendation', 'Keine Empfehlung verfügbar')
        
        lines = []
        lines.append("╔" + "═" * 63 + "╗")
        lines.append("║" + " " * 15 + bold("🪂 GLEITSCHIRM FLUG-TICKER") + " " * 15 + "║")
        lines.append("╚" + "═" * 63 + "╝")
        lines.append("")
        lines.append(f"📍 Startplatz: {bold(location)}")
        if date:
            date_display = datetime.strptime(date, "%Y-%m-%d").strftime("%d.%m.%Y")
            lines.append(f"📅 Tag: {date_display} ({FLIGHT_HOURS_START:02d}:00-{FLIGHT_HOURS_END:02d}:00)")
        lines.append(f"🕐 Analyse: {timestamp_str}")
        lines.append("")
        lines.append("━" * 65)
        lines.append("")
        lines.append(f"{condition_icon} {flyable_text} - {conditions_text}")
        lines.append("")
        lines.append(f"Bewertung: {rating_stars} ({rating}/10)")
        lines.append(f"Konfidenz:  {color(rating_bar, Colors.CYAN)} ({confidence}/10)")
        lines.append("")
        lines.append("━" * 65)
        lines.append("")
        lines.append(bold("📝 Zusammenfassung:"))
        lines.append(summary)
        lines.append("")
        lines.append("━" * 65)
        lines.append("")
        lines.append(bold("💨 Wind:"))
        lines.append(details.get('wind', 'Nicht verfügbar'))
        lines.append("")
        lines.append(bold("☁️ Thermik:"))
        lines.append(details.get('thermik', 'Nicht verfügbar'))
        lines.append("")
        lines.append(bold("⚠️  Risiken:"))
        lines.append(details.get('risks', 'Nicht verfügbar'))
        lines.append("")
        lines.append("━" * 65)
        lines.append("")
        lines.append(bold("💡 Empfehlung:"))
        lines.append(recommendation)
        lines.append("")
        lines.append("━" * 65)
        
        return "\n".join(lines)
    
    def print_result(self, result: Dict, use_colors: bool = True) -> None:
        """Gibt das Ergebnis formatiert im Terminal aus."""
        print(self.format_terminal_output(result, use_colors))
    
    def print_all_results(self, results: List[Dict], use_colors: bool = True) -> None:
        """Gibt mehrere Ergebnisse formatiert im Terminal aus."""
        for i, result in enumerate(results, 1):
            if i > 1:
                print("\n\n")  # Trennung zwischen Tagen
            self.print_result(result, use_colors)
    
    def _save_evaluations_to_json(self, results: List[Dict]) -> None:
        """Speichert Evaluierungen in JSON-Datei."""
        evaluations_file = get_evaluations_json_path()
        
        # Erstelle JSON-Struktur
        json_data = {
            "last_updated": datetime.now().isoformat(),
            "location": LOCATION.get('name', 'Uetliberg'),
            "evaluations": results
        }
        
        # Speichere in Datei
        try:
            with open(evaluations_file, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, ensure_ascii=False, indent=2)
            logger.info(f"Evaluierungen gespeichert in {evaluations_file}")
        except Exception as e:
            logger.error(f"Fehler beim Speichern der Evaluierungen: {e}")
            raise


def main():
    """CLI Entry Point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Gleitschirm Flugbarkeits-Evaluierung für Uetliberg")
    parser.add_argument("--json", action="store_true", help="Ausgabe als JSON")
    parser.add_argument("--no-color", action="store_true", help="Keine Farben")
    parser.add_argument("--model", type=str, default=None, help="OpenAI Model")
    parser.add_argument("--day", type=int, default=None, help="Nur einen bestimmten Tag anzeigen (1-basiert)")
    
    args = parser.parse_args()
    
    try:
        evaluator = LocationEvaluator(model=args.model)
        results = evaluator.analyze()
        
        # Filtere auf bestimmten Tag falls angegeben
        if args.day is not None:
            if 1 <= args.day <= len(results):
                results = [results[args.day - 1]]
            else:
                print(f"❌ Fehler: Tag {args.day} nicht verfügbar (verfügbar: 1-{len(results)})")
                exit(1)
        
        if args.json:
            print(json.dumps(results, indent=2, ensure_ascii=False))
        else:
            if len(results) == 1:
                evaluator.print_result(results[0], use_colors=not args.no_color)
            else:
                evaluator.print_all_results(results, use_colors=not args.no_color)
    except Exception as e:
        logger.error(f"Fehler: {e}")
        print(f"❌ Fehler: {e}")
        exit(1)


if __name__ == "__main__":
    main()
