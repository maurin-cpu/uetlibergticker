"""
Vercel Serverless Function für täglichen Cron-Job
Führt fetch_weather.py, location_evaluator.py und email_notifier.py aus.
"""

import os
import sys
import json
import logging
from datetime import datetime

# Füge Projekt-Root zum Python-Path hinzu
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def handler(request):
    """
    Vercel Serverless Function Handler.
    
    Führt die drei Skripte nacheinander aus:
    1. fetch_weather.py - Wetterdaten abrufen
    2. location_evaluator.py - LLM-Analyse durchführen
    3. email_notifier.py - E-Mail senden (wird automatisch von location_evaluator aufgerufen)
    
    Args:
        request: Vercel Request-Objekt
    
    Returns:
        JSON Response mit Status-Informationen
    """
    start_time = datetime.now()
    results = {
        'success': False,
        'timestamp': start_time.isoformat(),
        'steps': {},
        'errors': []
    }
    
    try:
        # Schritt 1: Wetterdaten abrufen
        logger.info("=" * 60)
        logger.info("SCHRITT 1: Wetterdaten abrufen")
        logger.info("=" * 60)
        
        try:
            from fetch_weather import fetch_weather_for_location
            
            # Für Vercel: Speichere in /tmp
            weather_data = fetch_weather_for_location(
                save_to_file=True,
                output_path='/tmp/wetterdaten.json'
            )
            
            if weather_data:
                results['steps']['fetch_weather'] = {
                    'success': True,
                    'message': f"Wetterdaten erfolgreich abgerufen für {len(list(weather_data.values())[0].get('hourly_data', {})))} Zeitstempel"
                }
                logger.info("✓ Wetterdaten erfolgreich abgerufen")
            else:
                raise Exception("Keine Wetterdaten zurückgegeben")
                
        except Exception as e:
            error_msg = f"Fehler beim Abrufen der Wetterdaten: {str(e)}"
            logger.error(error_msg)
            results['steps']['fetch_weather'] = {
                'success': False,
                'error': error_msg
            }
            results['errors'].append(error_msg)
            raise Exception(error_msg)
        
        # Schritt 2: LLM-Analyse durchführen
        logger.info("")
        logger.info("=" * 60)
        logger.info("SCHRITT 2: LLM-Analyse durchführen")
        logger.info("=" * 60)
        
        try:
            from location_evaluator import LocationEvaluator
            
            # Verwende /tmp für Wetterdaten
            evaluator = LocationEvaluator(weather_json_path='/tmp/wetterdaten.json')
            analysis_results = evaluator.analyze()
            
            if analysis_results:
                results['steps']['location_evaluator'] = {
                    'success': True,
                    'message': f"Analyse erfolgreich für {len(analysis_results)} Tag(e)",
                    'days_analyzed': len(analysis_results),
                    'results': [
                        {
                            'date': r.get('date'),
                            'conditions': r.get('conditions'),
                            'flyable': r.get('flyable'),
                            'rating': r.get('rating')
                        }
                        for r in analysis_results
                    ]
                }
                logger.info(f"✓ Analyse erfolgreich für {len(analysis_results)} Tag(e)")
            else:
                raise Exception("Keine Analyse-Ergebnisse zurückgegeben")
                
        except Exception as e:
            error_msg = f"Fehler bei der LLM-Analyse: {str(e)}"
            logger.error(error_msg)
            results['steps']['location_evaluator'] = {
                'success': False,
                'error': error_msg
            }
            results['errors'].append(error_msg)
            # Weiterlaufen, da E-Mails möglicherweise trotzdem gesendet werden können
        
        # Schritt 3: E-Mail-Benachrichtigungen (werden bereits von location_evaluator gesendet)
        logger.info("")
        logger.info("=" * 60)
        logger.info("SCHRITT 3: E-Mail-Benachrichtigungen")
        logger.info("=" * 60)
        
        # E-Mails werden bereits von location_evaluator.analyze_day() gesendet
        # Hier nur Status-Logging
        if 'location_evaluator' in results['steps'] and results['steps']['location_evaluator'].get('success'):
            results['steps']['email_notifier'] = {
                'success': True,
                'message': f"E-Mail-Benachrichtigungen wurden für {len(analysis_results)} Tag(e) gesendet"
            }
            logger.info(f"✓ E-Mail-Benachrichtigungen für {len(analysis_results)} Tag(e)")
        else:
            results['steps']['email_notifier'] = {
                'success': False,
                'message': "E-Mail-Benachrichtigungen konnten nicht gesendet werden (Analyse fehlgeschlagen)"
            }
        
        # Gesamt-Status
        all_steps_successful = all(
            step.get('success', False) 
            for step in results['steps'].values()
        )
        
        results['success'] = all_steps_successful
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        results['duration_seconds'] = duration
        
        logger.info("")
        logger.info("=" * 60)
        logger.info(f"CRON-JOB ABGESCHLOSSEN ({duration:.2f}s)")
        logger.info("=" * 60)
        
        if results['success']:
            logger.info("✓ Alle Schritte erfolgreich abgeschlossen")
        else:
            logger.warning("⚠ Einige Schritte hatten Fehler")
        
        # HTTP Response für Vercel Python Functions
        # Vercel Python Functions können ein Dict zurückgeben
        status_code = 200 if results['success'] else 500
        
        # Für Vercel: Return als Dict mit statusCode und body
        return {
            'statusCode': status_code,
            'body': json.dumps(results, ensure_ascii=False, indent=2),
            'headers': {
                'Content-Type': 'application/json; charset=utf-8'
            }
        }
        
    except Exception as e:
        error_msg = f"Unerwarteter Fehler im Cron-Job: {str(e)}"
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
# Für Python Serverless Functions verwenden wir 'handler'
def app(request):
    """Alternative Handler-Funktion für Vercel."""
    return handler(request)

