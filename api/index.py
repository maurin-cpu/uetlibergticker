"""
Vercel Serverless Function für das Web-Interface
Flask-App Export für Vercel Flask-Framework
"""

import sys
from pathlib import Path

# Füge Projekt-Root zum Python-Pfad hinzu
sys.path.insert(0, str(Path(__file__).parent.parent))

# Importiere Flask-App aus web.py
# Vercel erwartet eine Variable namens 'app' bei Flask-Framework
from web import app
