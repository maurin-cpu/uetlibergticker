"""
Vercel Serverless Function für das Web-Interface
"""

import sys
import os
from pathlib import Path

# Flask-App initialisieren
try:
    # Füge Projekt-Root zum Python-Pfad hinzu
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))
    
    # Stelle sicher, dass Flask das templates-Verzeichnis findet
    # Wichtig: Vercel ändert das Arbeitsverzeichnis, daher verwenden wir absoluten Pfad
    original_cwd = os.getcwd()
    os.chdir(str(project_root))
    
    # Prüfe ob templates-Verzeichnis existiert
    templates_dir = project_root / 'templates'
    if not templates_dir.exists():
        print(f"WARNUNG: templates-Verzeichnis nicht gefunden: {templates_dir}")
    
    from web import app
    
except Exception as e:
    # Fehlerbehandlung für bessere Debugging-Informationen
    import traceback
    error_msg = f"Fehler beim Initialisieren der Flask-App: {str(e)}\n{traceback.format_exc()}"
    print(error_msg)
    
    # Erstelle einen minimalen Error-Handler
    from flask import Flask
    app = Flask(__name__)
    
    @app.route('/')
    @app.route('/<path:path>')
    def error_handler(path=''):
        return f"<h1>Fehler beim Laden der Anwendung</h1><pre>{error_msg}</pre>", 500


def handler(request):
    """
    Vercel Serverless Function Handler für Flask-App.
    
    Verwendet serverless-wsgi um die Flask-App als WSGI-App aufzurufen.
    
    Args:
        request: Vercel Request-Objekt
    
    Returns:
        Vercel Response-Objekt mit statusCode, headers, body
    """
    try:
        from serverless_wsgi import handle_request
        
        # Verwende serverless-wsgi um die Flask-App aufzurufen
        return handle_request(app, request)
        
    except ImportError:
        # Fallback falls serverless-wsgi nicht verfügbar ist
        import traceback
        error_msg = f"serverless-wsgi nicht verfügbar. Bitte installieren Sie es mit: pip install serverless-wsgi\n{traceback.format_exc()}"
        print(error_msg)
        
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'text/html; charset=utf-8'},
            'body': f"<h1>Internal Server Error</h1><pre>{error_msg}</pre>"
        }
    except Exception as e:
        import traceback
        error_msg = f"Fehler im Handler: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'text/html; charset=utf-8'},
            'body': f"<h1>Internal Server Error</h1><pre>{error_msg}</pre>"
        }

