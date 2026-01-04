"""
Vercel Serverless Function für das Web-Interface
"""

import sys
import os
from pathlib import Path

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
    
    # Exportiere die Flask-App für Vercel
    # Vercel erwartet ein 'handler' Objekt für Flask-Apps
    handler = app
    
except Exception as e:
    # Fehlerbehandlung für bessere Debugging-Informationen
    import traceback
    error_msg = f"Fehler beim Initialisieren der Flask-App: {str(e)}\n{traceback.format_exc()}"
    print(error_msg)
    
    # Erstelle einen minimalen Error-Handler
    from flask import Flask
    error_app = Flask(__name__)
    
    @error_app.route('/')
    @error_app.route('/<path:path>')
    def error_handler(path=''):
        return f"<h1>Fehler beim Laden der Anwendung</h1><pre>{error_msg}</pre>", 500
    
    handler = error_app

