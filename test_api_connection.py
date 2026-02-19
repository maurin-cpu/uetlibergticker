#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Kurzer Test um die OpenAI API-Verbindung zu prüfen
"""

import os
import sys

# Lade .env falls vorhanden
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from location_evaluator import LocationEvaluator

print("=" * 60)
print("API-CONNECTION TEST")
print("=" * 60)

# Prüfe API-Key
api_key = os.environ.get('OPENAI_API_KEY')
if not api_key:
    print("[FEHLER] OPENAI_API_KEY nicht gesetzt!")
    print("Bitte setzen Sie die Umgebungsvariable OPENAI_API_KEY")
    sys.exit(1)

if not api_key.startswith('sk-'):
    print(f"[WARNUNG] API-Key Format könnte falsch sein (sollte mit 'sk-' beginnen)")

print(f"[OK] API-Key gefunden (Länge: {len(api_key)} Zeichen)")

# Teste ob Wetterdaten vorhanden sind
try:
    evaluator = LocationEvaluator()
    print("[OK] LocationEvaluator initialisiert")
    
    # Lade Wetterdaten
    weather_data = evaluator._load_weather_data()
    print(f"[OK] Wetterdaten geladen")
    
    # Teste Prompt-Building mit echten Daten
    hourly_data = weather_data.get('hourly_data', {})
    if not hourly_data:
        print("[FEHLER] Keine stündlichen Wetterdaten gefunden!")
        sys.exit(1)
    
    # Nimm ersten Tag
    from datetime import datetime
    days_data = {}
    for timestamp, data in hourly_data.items():
        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        date_key = dt.strftime("%Y-%m-%d")
        if date_key not in days_data:
            days_data[date_key] = {}
        days_data[date_key][timestamp] = data
    
    if not days_data:
        print("[FEHLER] Keine Tagesdaten gefunden!")
        sys.exit(1)
    
    first_date = sorted(days_data.keys())[0]
    day_data = days_data[first_date]
    
    print(f"[OK] Teste mit Datum: {first_date}")
    print(f"  Stunden im Datum: {len(day_data)}")
    
    # Teste Prompt-Building
    from config import LOCATION
    location_data = {
        'name': LOCATION['name'],
        'fluggebiet': LOCATION['fluggebiet'],
        'typ': LOCATION['typ'],
        'windrichtung': LOCATION['windrichtung'],
        'bemerkung': LOCATION['bemerkung'],
        'hourly_data': day_data,
        'pressure_level_data': {},
        'date': first_date
    }
    
    system_prompt, user_prompt = evaluator._build_prompt(location_data)
    print(f"[OK] Prompt erstellt")
    print(f"  System-Prompt: {len(system_prompt)} Zeichen")
    print(f"  User-Prompt: {len(user_prompt)} Zeichen")
    
    # Prüfe ob Windrichtungs-Info korrekt ist
    if "NICHT über 360° hinaus" in user_prompt:
        print("[OK] Windrichtungs-Interpretation korrekt im Prompt")
    if "0° bis 90°" in user_prompt or "EXAKT: 0° bis 90°" in user_prompt:
        print("[OK] Korrekte Windrichtungs-Range (0°-90°) im Prompt")
    
    print("\n" + "=" * 60)
    print("Bereit für API-Call")
    print("=" * 60)
    print("\nMöchten Sie einen echten API-Call durchführen? (kostet API-Credits)")
    print("Falls ja, führen Sie aus: python location_evaluator.py --day 1")
    
except Exception as e:
    print(f"\n[FEHLER] {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
