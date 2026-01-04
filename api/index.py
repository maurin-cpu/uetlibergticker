"""
Vercel Serverless Function für das Web-Interface
"""

import sys
import os
from pathlib import Path

# Füge Projekt-Root zum Python-Pfad hinzu (nur einmal beim Laden)
_project_root = Path(__file__).parent.parent
sys.path.insert(0, str(_project_root))
os.chdir(str(_project_root))

# Flask-App wird lazy geladen um issubclass()-Fehler zu vermeiden
_flask_app = None


def _get_flask_app():
    """Lazy-Loading der Flask-App."""
    global _flask_app
    if _flask_app is None:
        try:
            from web import app
            _flask_app = app
        except Exception as e:
            import traceback
            error_msg = f"Fehler beim Laden der Flask-App: {str(e)}\n{traceback.format_exc()}"
            print(error_msg)
            
            from flask import Flask
            _flask_app = Flask(__name__)
            
            @_flask_app.route('/')
            @_flask_app.route('/<path:path>')
            def error_handler(path=''):
                return f"<h1>Fehler beim Laden der Anwendung</h1><pre>{error_msg}</pre>", 500
    
    return _flask_app


def handler(request):
    """
    Vercel Serverless Function Handler für Flask-App.
    
    Args:
        request: Vercel Request-Objekt
    
    Returns:
        Vercel Response-Objekt mit statusCode, headers, body
    """
    try:
        from serverless_wsgi import handle_request
        
        # Lade Flask-App lazy
        flask_app = _get_flask_app()
        
        # Verwende serverless-wsgi um die Flask-App aufzurufen
        return handle_request(flask_app, request)
        
    except ImportError as e:
        import traceback
        error_msg = f"Import-Fehler: {str(e)}\n{traceback.format_exc()}"
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

