"""
Vercel Serverless Function für automatische E-Mail-Benachrichtigungen
Kann von einem Cron-Service alle 10 Minuten aufgerufen werden
"""

import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path

# Füge Projekt-Root zum Python-Path hinzu
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Lade .env Datei explizit
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def handler(request):
    """
    Vercel Serverless Function Handler für automatische E-Mail-Benachrichtigungen.

    Sendet E-Mails basierend auf den neuesten Evaluierungen.
    Falls keine Evaluierungen vorhanden sind, wird zuerst der Cron-Job ausgeführt.

    Args:
        request: Vercel Request-Objekt

    Returns:
        JSON Response mit Status-Informationen
    """
    start_time = datetime.now()
    results = {
        'success': False,
        'timestamp': start_time.isoformat(),
        'emails_sent': 0,
        'errors': []
    }

    try:
        from email_notifier import EmailNotifier

        # Prüfe ob EmailNotifier verfügbar ist
        if not EmailNotifier:
            error_msg = "E-Mail-Modul nicht verfügbar"
            logger.error(error_msg)
            results['errors'].append(error_msg)
            return {
                'statusCode': 500,
                'body': json.dumps(results, ensure_ascii=False, indent=2),
                'headers': {
                    'Content-Type': 'application/json; charset=utf-8'
                }
            }

        # Initialisiere E-Mail-Notifier
        notifier = EmailNotifier()

        if not notifier.enabled:
            error_msg = "E-Mail-Benachrichtigung deaktiviert: Fehlende Konfiguration in Environment Variables"
            logger.error(error_msg)
            results['errors'].append(error_msg)

            # Zeige welche Felder fehlen
            config_status = notifier.check_configuration()
            if config_status['missing_fields']:
                error_msg += f". Fehlende Felder: {', '.join(config_status['missing_fields'])}"

            return {
                'statusCode': 400,
                'body': json.dumps(results, ensure_ascii=False, indent=2),
                'headers': {
                    'Content-Type': 'application/json; charset=utf-8'
                }
            }

        # Lade Evaluierungen aus evaluations.json
        evaluations_file = None
        if os.path.exists('/tmp') and Path('/tmp/evaluations.json').exists():
            evaluations_file = Path('/tmp/evaluations.json')
        elif Path("data/evaluations.json").exists():
            evaluations_file = Path("data/evaluations.json")

        if not evaluations_file or not evaluations_file.exists():
            # Keine Evaluierungen vorhanden - führe Cron-Job aus
            logger.info("Keine Evaluierungen gefunden - führe Cron-Job aus")

            try:
                # Importiere und führe Cron-Handler aus
                from api.cron import handler as cron_handler
                cron_result = cron_handler(request)

                # Prüfe ob Cron-Job erfolgreich war
                cron_body = json.loads(cron_result['body'])
                if not cron_body.get('success'):
                    error_msg = "Cron-Job fehlgeschlagen - keine E-Mails gesendet"
                    logger.error(error_msg)
                    results['errors'].append(error_msg)
                    results['cron_result'] = cron_body
                    return {
                        'statusCode': 500,
                        'body': json.dumps(results, ensure_ascii=False, indent=2),
                        'headers': {
                            'Content-Type': 'application/json; charset=utf-8'
                        }
                    }

                logger.info("Cron-Job erfolgreich ausgeführt")
                results['cron_executed'] = True

                # Versuche erneut Evaluierungen zu laden
                if os.path.exists('/tmp') and Path('/tmp/evaluations.json').exists():
                    evaluations_file = Path('/tmp/evaluations.json')
                elif Path("data/evaluations.json").exists():
                    evaluations_file = Path("data/evaluations.json")

            except Exception as e:
                error_msg = f"Fehler beim Ausführen des Cron-Jobs: {str(e)}"
                logger.error(error_msg, exc_info=True)
                results['errors'].append(error_msg)
                return {
                    'statusCode': 500,
                    'body': json.dumps(results, ensure_ascii=False, indent=2),
                    'headers': {
                        'Content-Type': 'application/json; charset=utf-8'
                    }
                }

        # Lade Evaluierungen
        if not evaluations_file or not evaluations_file.exists():
            error_msg = "Keine Evaluierungen verfügbar - kann keine E-Mails senden"
            logger.error(error_msg)
            results['errors'].append(error_msg)
            return {
                'statusCode': 404,
                'body': json.dumps(results, ensure_ascii=False, indent=2),
                'headers': {
                    'Content-Type': 'application/json; charset=utf-8'
                }
            }

        try:
            with open(evaluations_file, 'r', encoding='utf-8') as f:
                evaluations_data = json.load(f)
        except Exception as e:
            error_msg = f"Fehler beim Laden der Evaluierungen: {str(e)}"
            logger.error(error_msg)
            results['errors'].append(error_msg)
            return {
                'statusCode': 500,
                'body': json.dumps(results, ensure_ascii=False, indent=2),
                'headers': {
                    'Content-Type': 'application/json; charset=utf-8'
                }
            }

        # Extrahiere Evaluierungen
        evaluations_list = evaluations_data.get('evaluations', [])

        if not evaluations_list:
            error_msg = "Keine Evaluierungen in evaluations.json gefunden"
            logger.warning(error_msg)
            results['errors'].append(error_msg)
            return {
                'statusCode': 404,
                'body': json.dumps(results, ensure_ascii=False, indent=2),
                'headers': {
                    'Content-Type': 'application/json; charset=utf-8'
                }
            }

        # Sende E-Mails für alle Evaluierungen (mit force_send=True für Tests)
        emails_sent = 0
        email_results = []

        for evaluation in evaluations_list:
            date = evaluation.get('date', 'Unbekannt')

            # Sende E-Mail mit force_send=True (ignoriert EXCELLENT/GOOD Check)
            success, error_msg = notifier.send_alert(evaluation, force_send=True)

            if success:
                emails_sent += 1
                email_results.append({
                    'date': date,
                    'status': 'success',
                    'conditions': evaluation.get('conditions')
                })
                logger.info(f"E-Mail erfolgreich gesendet für {date}")
            else:
                email_results.append({
                    'date': date,
                    'status': 'failed',
                    'error': error_msg
                })
                logger.error(f"E-Mail-Versand fehlgeschlagen für {date}: {error_msg}")
                results['errors'].append(f"E-Mail für {date}: {error_msg}")

        results['emails_sent'] = emails_sent
        results['email_results'] = email_results
        results['total_evaluations'] = len(evaluations_list)
        results['success'] = emails_sent > 0

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        results['duration_seconds'] = duration

        logger.info(f"Auto-E-Mail Job abgeschlossen: {emails_sent}/{len(evaluations_list)} E-Mails gesendet")

        status_code = 200 if results['success'] else 500

        return {
            'statusCode': status_code,
            'body': json.dumps(results, ensure_ascii=False, indent=2),
            'headers': {
                'Content-Type': 'application/json; charset=utf-8'
            }
        }

    except Exception as e:
        error_msg = f"Unerwarteter Fehler im Auto-E-Mail Job: {str(e)}"
        logger.error(error_msg, exc_info=True)

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        results['duration_seconds'] = duration
        results['errors'].append(error_msg)

        return {
            'statusCode': 500,
            'body': json.dumps(results, ensure_ascii=False, indent=2),
            'headers': {
                'Content-Type': 'application/json; charset=utf-8'
            }
        }


# Vercel erwartet eine Funktion namens 'handler' oder 'app'
def app(request):
    """Alternative Handler-Funktion für Vercel."""
    return handler(request)
