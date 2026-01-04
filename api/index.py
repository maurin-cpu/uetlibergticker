"""
Vercel Serverless Function für das Web-Interface
"""

import sys
from pathlib import Path

# Füge Projekt-Root zum Python-Pfad hinzu
sys.path.insert(0, str(Path(__file__).parent.parent))

from web import app

# Exportiere die Flask-App für Vercel
# Vercel erwartet ein 'handler' Objekt
handler = app

