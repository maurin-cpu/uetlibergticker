#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test-Skript um zu prüfen, ob das System funktioniert
"""

import sys
import os

print("=" * 60)
print("SYSTEM-TEST für Uetliberg Ticker")
print("=" * 60)

# Test 1: Basis-Imports
print("\n[1/6] Teste Basis-Imports...")
try:
    import requests
    import json
    import logging
    from datetime import datetime
    from pathlib import Path
    print("[OK] Basis-Imports erfolgreich")
except ImportError as e:
    print(f"[FEHLER] Fehler bei Basis-Imports: {e}")
    sys.exit(1)

# Test 2: Config-Import
print("\n[2/6] Teste Config-Import...")
try:
    from config import (
        LOCATION,
        LLM_USER_PROMPT_TEMPLATE,
        LLM_SYSTEM_PROMPT,
        FLIGHT_HOURS_START,
        FLIGHT_HOURS_END,
        get_weather_json_path,
        get_evaluations_json_path
    )
    print("[OK] Config-Import erfolgreich")
    print(f"  Location: {LOCATION['name']}")
    print(f"  Windrichtung: {LOCATION['windrichtung']}")
    print(f"  Flugstunden: {FLIGHT_HOURS_START:02d}:00-{FLIGHT_HOURS_END:02d}:00")
except ImportError as e:
    print(f"[FEHLER] Fehler bei Config-Import: {e}")
    sys.exit(1)

# Test 3: Prompt-Template Validierung
print("\n[3/6] Teste Prompt-Template...")
try:
    # Test ob {besonderheiten} im Template vorhanden ist
    if "{besonderheiten}" in LLM_USER_PROMPT_TEMPLATE:
        print("[OK] Platzhalter {besonderheiten} gefunden")
    else:
        print("[FEHLER] Platzhalter {besonderheiten} NICHT gefunden!")
    
    # Test ob alle Platzhalter vorhanden sind
    required_placeholders = ["{name}", "{fluggebiet}", "{typ}", "{windrichtung}", "{besonderheiten}", 
                             "{hourly_data}", "{total_hours}", "{flight_hours_start}", "{flight_hours_end}"]
    missing = [p for p in required_placeholders if p not in LLM_USER_PROMPT_TEMPLATE]
    if missing:
        print(f"[FEHLER] Fehlende Platzhalter: {missing}")
    else:
        print("[OK] Alle erforderlichen Platzhalter vorhanden")
    
    # Test Windrichtungs-Interpretation
    if "NICHT über 360° hinaus" in LLM_USER_PROMPT_TEMPLATE:
        print("[OK] Windrichtungs-Interpretation korrekt aktualisiert")
    else:
        print("[WARNUNG] Windrichtungs-Interpretation könnte unklar sein")
        
except Exception as e:
    print(f"[FEHLER] Fehler bei Prompt-Template-Test: {e}")
    sys.exit(1)

# Test 4: Wetterdaten-Datei
print("\n[4/6] Teste Wetterdaten-Datei...")
try:
    weather_path = get_weather_json_path()
    print(f"  Pfad: {weather_path}")
    
    if weather_path.exists():
        with open(weather_path, 'r', encoding='utf-8') as f:
            weather_data = json.load(f)
        
        # Suche Uetliberg Eintrag
        uetliberg_found = False
        for key in weather_data.keys():
            if 'uetliberg' in key.lower() or 'balderen' in key.lower():
                uetliberg_found = True
                hourly_data = weather_data[key].get('hourly_data', {})
                print(f"[OK] Wetterdaten gefunden: {key}")
                print(f"  Stunden-Datenpunkte: {len(hourly_data)}")
                if hourly_data:
                    first_timestamp = sorted(hourly_data.keys())[0]
                    print(f"  Erste Stunde: {first_timestamp}")
                break
        
        if not uetliberg_found:
            print("[FEHLER] Keine Uetliberg-Daten gefunden!")
            sys.exit(1)
    else:
        print(f"[FEHLER] Wetterdaten-Datei nicht gefunden: {weather_path}")
        sys.exit(1)
except Exception as e:
    print(f"[FEHLER] Fehler beim Laden der Wetterdaten: {e}")
    sys.exit(1)

# Test 5: Location Evaluator Import
print("\n[5/6] Teste Location Evaluator Import...")
try:
    from location_evaluator import LocationEvaluator
    print("[OK] LocationEvaluator erfolgreich importiert")
    
    # Prüfe ob API-Key gesetzt ist (ohne ihn zu verwenden)
    api_key = os.environ.get('OPENAI_API_KEY')
    if api_key:
        if api_key.startswith('sk-'):
            print(f"[OK] OPENAI_API_KEY gefunden (beginnt mit 'sk-')")
        else:
            print(f"[WARNUNG] OPENAI_API_KEY gefunden, aber Format könnte falsch sein")
    else:
        print("[WARNUNG] OPENAI_API_KEY nicht gesetzt (wird für LLM-Calls benötigt)")
        
except ImportError as e:
    print(f"[FEHLER] Fehler bei LocationEvaluator-Import: {e}")
    sys.exit(1)
except Exception as e:
    print(f"[FEHLER] Fehler: {e}")
    sys.exit(1)

# Test 6: Prompt-Building Test (ohne API-Call)
print("\n[6/6] Teste Prompt-Building...")
try:
    # Erstelle Mock-Daten
    mock_location_data = {
        'name': LOCATION['name'],
        'fluggebiet': LOCATION['fluggebiet'],
        'typ': LOCATION['typ'],
        'windrichtung': LOCATION['windrichtung'],
        'bemerkung': LOCATION['bemerkung'],
        'hourly_data': {
            '2026-02-01T09:00': {
                'temperature_2m': 5.0,
                'wind_speed_10m': 15.0,
                'wind_direction_10m': 45,
                'wind_gusts_10m': 20.0,
                'cloud_base': 1500.0,
                'cloud_cover': 50
            }
        },
        'pressure_level_data': {},
        'date': '2026-02-01'
    }
    
    evaluator = LocationEvaluator()
    system_prompt, user_prompt = evaluator._build_prompt(mock_location_data)
    
    print(f"[OK] Prompt erfolgreich erstellt")
    print(f"  System-Prompt Länge: {len(system_prompt)} Zeichen")
    print(f"  User-Prompt Länge: {len(user_prompt)} Zeichen")
    
    # Prüfe ob besonderheiten korrekt eingefügt wurde
    if "Benötigt gewisse Windstärke" in user_prompt or "Keine" in user_prompt:
        print("[OK] Besonderheiten wurden korrekt eingefügt")
    else:
        print("[WARNUNG] Besonderheiten könnten fehlen")
    
    # Prüfe Windrichtungs-Interpretation
    if "0° bis 90°" in user_prompt or "N-O" in user_prompt:
        print("[OK] Windrichtungs-Info vorhanden")
    
except Exception as e:
    print(f"[FEHLER] Fehler beim Prompt-Building: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 60)
print("[OK] ALLE TESTS ERFOLGREICH!")
print("=" * 60)
print("\nDas System ist bereit für die Verwendung.")
print("Hinweis: Für einen vollständigen Test mit LLM-Call benötigen Sie einen gesetzten OPENAI_API_KEY.")
