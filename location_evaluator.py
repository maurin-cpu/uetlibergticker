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

from config import (
    LLM_SYSTEM_PROMPT, 
    LLM_USER_PROMPT_TEMPLATE, 
    LOCATION,
    FORECAST_DAYS,
    FLIGHT_HOURS_START,
    FLIGHT_HOURS_END
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
    
    def __init__(self, weather_json_path: str = "data/wetterdaten.json", model: str = None):
        self.weather_json_path = weather_json_path
        self.model = model or os.environ.get('OPENAI_MODEL', 'gpt-4')
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
        
        # Gruppiere nach Tagen und filtere Flugstunden
        days_data = self._group_by_days(hourly_data)
        
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
        
        return results
    
    def analyze_day(self, day_data: Dict, date: str) -> Dict:
        """Analysiert einen einzelnen Tag."""
        # Kombiniere mit Standort-Info aus config.py
        location_data = {
            'name': LOCATION['name'],
            'fluggebiet': LOCATION['fluggebiet'],
            'typ': LOCATION['typ'],
            'windrichtung': LOCATION['windrichtung'],
            'bemerkung': LOCATION['bemerkung'],
            'hourly_data': day_data,
            'date': date
        }

        # LLM-Analyse durchführen
        try:
            result = self._analyze_with_llm(location_data)
            result['location'] = LOCATION['name']
            result['date'] = date
            result['timestamp'] = datetime.now().isoformat()
            
            # E-Mail-Benachrichtigung senden (immer, da force_send=True als Standard)
            if self.email_notifier:
                try:
                    success, error_msg = self.email_notifier.send_alert(result, force_send=True)
                    if not success and error_msg:
                        logger.warning(f"E-Mail-Benachrichtigung fehlgeschlagen für {date}: {error_msg}")
                    else:
                        logger.info(f"E-Mail-Benachrichtigung erfolgreich gesendet für {date}")
                except Exception as e:
                    logger.warning(f"Fehler beim Senden der E-Mail-Benachrichtigung für {date}: {e}")
            
            return result
        except Exception as e:
            logger.error(f"Fehler bei LLM-Analyse für {date}: {e}")
            return {
                "flyable": False,
                "rating": 0,
                "confidence": 0,
                "conditions": "DANGEROUS",
                "summary": f"Fehler: {str(e)}",
                "details": {"wind": "", "thermik": "", "risks": f"Systemfehler: {str(e)}"},
                "recommendation": "Bitte später erneut versuchen.",
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
    
    def _group_by_days(self, hourly_data: Dict) -> Dict[str, Dict]:
        """Gruppiert Stunden-Daten nach Tagen und filtert auf Flugstunden."""
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
        
        # Filtere dann innerhalb jedes Tages auf Flugstunden
        filtered_days_data = {}
        for date_key, day_hourly_data in days_data.items():
            flight_hours_data = self._filter_flight_hours(day_hourly_data, FLIGHT_HOURS_START, FLIGHT_HOURS_END)
            # Behalte auch Tage ohne Flugstunden-Daten (mit leerem Dict)
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
    
    def _format_hourly_data(self, hourly_data: Dict, hours: int = 6) -> str:
        """Formatiert stündliche Daten für Prompt."""
        if not hourly_data:
            return "Keine stündlichen Daten verfügbar"
        
        sorted_times = sorted(hourly_data.keys())[:hours]
        lines = []
        
        for timestamp in sorted_times:
            data = hourly_data[timestamp]
            time_str = timestamp.replace('T', ' ')[:16]
            
            temp = data.get('temperature_2m', 'N/A')
            wind_speed = data.get('wind_speed_10m', 'N/A')
            wind_dir = data.get('wind_direction_10m', 'N/A')
            wind_gusts = data.get('wind_gusts_10m', 'N/A')
            cloud_base = data.get('cloud_base', 'N/A')
            cloud_cover = data.get('cloud_cover', 'N/A')
            cape = data.get('cape', 'N/A')
            precip = data.get('precipitation', 'N/A')
            sunshine = data.get('sunshine_duration', 'N/A')
            
            if isinstance(sunshine, (int, float)) and sunshine > 0:
                sunshine_str = f"{sunshine / 3600:.1f}h"
            else:
                sunshine_str = "0h"
            
            line = (
                f"{time_str}: Temp {temp}°C | "
                f"Wind {wind_speed}km/h aus {wind_dir}° (Böen {wind_gusts}km/h) | "
                f"Wolkenbasis {cloud_base}m | Bewölkung {cloud_cover}% | "
                f"CAPE {cape} J/kg | Niederschlag {precip}mm | Sonne {sunshine_str}"
            )
            lines.append(line)
        
        return "\n".join(lines)
    
    def _build_prompt(self, location_data: Dict) -> Tuple[str, str]:
        """Erstellt System- und User-Prompt."""
        bemerkungen = location_data.get('bemerkung', '')
        bemerkungen_list = [b.strip() for b in bemerkungen.split('|') if b.strip()] if bemerkungen else []
        
        hourly_data = location_data.get('hourly_data', {})
        date = location_data.get('date', '')
        
        # Formatiere alle verfügbaren Stunden (nicht nur 6)
        formatted_hours = self._format_hourly_data(hourly_data, hours=len(hourly_data))
        
        # Erweitere User-Prompt um Flugstunden-Info
        flight_hours_info = f"\n\nWICHTIG: Diese Analyse bezieht sich nur auf Flugstunden ({FLIGHT_HOURS_START:02d}:00-{FLIGHT_HOURS_END:02d}:00) für {date}."
        
        user_prompt = LLM_USER_PROMPT_TEMPLATE.format(
            name=location_data.get('name', 'N/A'),
            fluggebiet=location_data.get('fluggebiet', 'N/A'),
            typ=location_data.get('typ', 'N/A'),
            windrichtung=location_data.get('windrichtung', 'Nicht angegeben'),
            besonderheiten=', '.join(bemerkungen_list) if bemerkungen_list else 'Keine',
            hourly_data=formatted_hours,
            wind_check_info="",
            total_hours=len(hourly_data)
        ) + flight_hours_info
        
        return LLM_SYSTEM_PROMPT, user_prompt
    
    def _analyze_with_llm(self, location_data: Dict) -> Dict:
        """Sendet aufbereitete Daten an OpenAI GPT."""
        system_prompt, user_prompt = self._build_prompt(location_data)
        
        url = "https://api.openai.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        
        json_supported_models = ["gpt-4-turbo", "gpt-4-turbo-preview", "gpt-4-0125-preview", "gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"]
        
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            "temperature": 0.3
        }
        
        if any(model in self.model for model in json_supported_models):
            payload["response_format"] = {"type": "json_object"}
        
        max_retries = 3
        retry_delay = 1
        
        for attempt in range(max_retries):
            try:
                response = requests.post(url, headers=headers, json=payload, timeout=30)
                
                if response.status_code == 200:
                    return self._parse_llm_response(response.json())
                elif response.status_code == 429:
                    wait_time = retry_delay * (2 ** attempt) * 2
                    logger.warning(f"Rate limit, warte {wait_time}s")
                    time.sleep(wait_time)
                    continue
                else:
                    if attempt == max_retries - 1:
                        raise Exception(f"API Fehler {response.status_code}: {response.text}")
                    time.sleep(retry_delay * (2 ** attempt))
            except requests.Timeout:
                if attempt == max_retries - 1:
                    raise Exception("OpenAI API Timeout")
                time.sleep(retry_delay * (2 ** attempt))
            except requests.RequestException as e:
                if attempt == max_retries - 1:
                    raise Exception(f"API Request-Fehler: {str(e)}")
                time.sleep(retry_delay * (2 ** attempt))
        
        raise Exception("OpenAI API Call fehlgeschlagen")
    
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
        result['confidence'] = int(result.get('confidence', 0))
        result['conditions'] = str(result.get('conditions', 'UNKNOWN'))
        
        if 'summary' not in result:
            result['summary'] = "Keine Zusammenfassung verfügbar"
        if 'recommendation' not in result:
            result['recommendation'] = "Keine Empfehlung verfügbar"
        
        return result
    
    def format_terminal_output(self, result: Dict, use_colors: bool = True) -> str:
        """Formatiert das Evaluierungs-Ergebnis für Terminal-Ausgabe."""
        def color(text: str, color_code: str) -> str:
            return f"{color_code}{text}{Colors.RESET}" if use_colors else text
        
        def bold(text: str) -> str:
            return f"{Colors.BOLD}{text}{Colors.RESET}" if use_colors else text
        
        conditions = result.get('conditions', 'UNKNOWN').upper()
        if conditions == 'EXCELLENT' or conditions == 'GOOD':
            condition_color = Colors.GREEN
            condition_icon = '✅'
        elif conditions == 'MODERATE':
            condition_color = Colors.YELLOW
            condition_icon = '⚠️'
        elif conditions == 'POOR':
            condition_color = Colors.ORANGE
            condition_icon = '❌'
        elif conditions == 'DANGEROUS':
            condition_color = Colors.RED
            condition_icon = '🚫'
        else:
            condition_color = Colors.YELLOW
            condition_icon = '❓'
        
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
        # Für Vercel: Verwende /tmp falls verfügbar, sonst data/
        if os.path.exists('/tmp'):
            data_dir = Path('/tmp')
        else:
            data_dir = Path("data")
            data_dir.mkdir(exist_ok=True)
        
        evaluations_file = data_dir / "evaluations.json"
        
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
