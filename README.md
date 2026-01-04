# Uetliberg Ticker - Wetterdaten für Gleitschirmflug-Standorte

Python-System zur Abfrage, Analyse und Evaluierung von Wettervorhersagen für Gleitschirmflug-Standorte über die MeteoSwiss ICON-CH API.

## Features

- **Wetterdaten-Abruf**: Automatischer Abruf von Wettervorhersagen für mehrere Standorte
- **Web-Interface**: Interaktive Visualisierung mit "Flyable Window Grid" Design
- **Terminal-Anzeige**: Übersichtliche Darstellung der Wetterdaten im Terminal
- **LLM-basierte Flugbarkeits-Evaluierung**: Intelligente Bewertung der Flugbedingungen durch GPT-4
- **E-Mail-Benachrichtigungen**: Automatische E-Mail-Alerts wenn die Konditionen EXCELLENT oder GOOD sind (optional)

## Schnellstart

### 1. Virtuelle Umgebung erstellen (empfohlen)

```bash
python -m venv .venv
```

### 2. Virtuelle Umgebung aktivieren

**Windows (PowerShell):**
```powershell
.venv\Scripts\Activate.ps1
```

**Windows (CMD):**
```cmd
.venv\Scripts\activate.bat
```

**Linux/Mac:**
```bash
source .venv/bin/activate
```

### 3. Abhängigkeiten installieren

```bash
pip install -r requirements.txt
```

### 4. OpenAI API Key konfigurieren

Erstelle eine `.env` Datei im Projektverzeichnis (siehe `.env.example`):

```bash
OPENAI_API_KEY=dein_api_key_hier
OPENAI_MODEL=gpt-4
```

**Wichtig:** Du benötigst einen OpenAI API Key für die Flugbarkeits-Evaluierung. Erhalte einen Key unter [platform.openai.com](https://platform.openai.com/api-keys).

### 4.1. E-Mail-Benachrichtigungen konfigurieren (optional)

Um E-Mail-Benachrichtigungen zu erhalten, wenn die Flugbarkeits-Konditionen EXCELLENT oder GOOD sind, füge folgende Variablen zur `.env` Datei hinzu:

```bash
# E-Mail-Konfiguration für Benachrichtigungen
EMAIL_SMTP_SERVER=smtp.gmail.com
EMAIL_SMTP_PORT=587
EMAIL_SENDER=deine.email@gmail.com
EMAIL_PASSWORD=dein_app_passwort
EMAIL_RECIPIENT=empfaenger@example.com
```

**Gmail Setup:**
1. Gehe zu deinem Google-Konto → Sicherheit
2. Aktiviere die 2-Faktor-Authentifizierung (falls noch nicht aktiviert)
3. Erstelle ein App-Passwort:
   - Gehe zu "App-Passwörter" (unter "2-Schritt-Verifizierung")
   - Wähle "Mail" und "Andere (Benutzerdefiniert)" → "Uetliberg Ticker"
   - Kopiere das generierte 16-stellige Passwort
4. Verwende dieses App-Passwort als `EMAIL_PASSWORD` in der `.env` Datei

**Hinweis:** Wenn die E-Mail-Konfiguration nicht gesetzt ist, wird das System ohne Fehler weiterlaufen, sendet aber keine E-Mails.

### 5. CSV-Datei mit Startplätzen vorbereiten

Erstelle eine CSV-Datei `data/startplaetze_schweiz.csv` mit folgenden Spalten:
- `Platz`: Name des Startplatzes
- `Latitude`: Breitengrad
- `Longitude`: Längengrad
- `Typ`: Typ des Startplatzes (optional)
- `Fluggebiet`: Name des Fluggebiets (optional)
- `Windrichtung/Ausrichtung`: Bevorzugte Windrichtung (optional)
- `Bemerkung`: Zusätzliche Bemerkungen (optional)

### 6. Wetterdaten abrufen

```bash
python fetch_weather.py
```

Dies erstellt eine `data/wetterdaten.json` Datei mit den aktuellen Wettervorhersagen.

### 7. Web-Interface öffnen

Öffne `index.html` direkt im Browser oder verwende einen lokalen Webserver:

```bash
# Mit Python's eingebautem Server
python -m http.server 8000

# Oder mit Node.js (falls installiert)
npx http-server
```

Das Web-Interface zeigt:
- **Wind**: Pfeile mit Richtung, Geschwindigkeit und Farbkodierung
- **Niederschlag**: Icons und Intensitäts-Balken
- **Thermik**: Vertikale Balken mit Blasen-Animation und Steigrate
- **Wolkenbasis**: Horizontlinie mit Wolken-Icons relativ zur Startplatzhöhe

Klicke/Tippe auf eine Zelle für detaillierte Informationen.

### 8. Wetterdaten im Terminal anzeigen

```bash
# Alle Standorte anzeigen
python display_weather.py

# Einzelnen Standort anzeigen
python display_weather.py "Standortname"
```

### 9. Flugbarkeits-Evaluierung durchführen

```bash
# Evaluierung für einen Startplatz (mit formatierter Terminal-Ausgabe)
python location_evaluator.py Uetliberg

# JSON-Ausgabe (für weitere Verarbeitung)
python location_evaluator.py Uetliberg --json

# Ohne Farben (für Logs)
python location_evaluator.py Uetliberg --no-color

# Anderes OpenAI Model verwenden
python location_evaluator.py Uetliberg --model gpt-4-turbo
```

**Wie es funktioniert:**
- Das Programm lädt Wetterdaten und Startplatz-Informationen
- Es bereitet die Daten strukturiert für das LLM auf
- **Das LLM (GPT-4) führt die gesamte Flugbarkeits-Analyse durch:**
  - Bewertet Wind, Thermik, Wolkenbasis, Niederschlag
  - Prüft lokale Besonderheiten (Luftraum, Topografie)
  - Gibt eine Bewertung (1-10), Konfidenz und Empfehlung
  - Entscheidet ob fliegbar oder nicht
- Das Programm zeigt das Ergebnis formatiert im Terminal an

## Projektstruktur

```
uetliberg_ticker/
├── fetch_weather.py          # Wetterdaten-Abruf (nur Daten-Aggregation)
├── index.html                # Web-Interface (Dashboard mit Sparklines)
├── display_weather.py        # Wetterdaten-Anzeige im Terminal
├── location_evaluator.py     # LLM-basierte Flugbarkeits-Evaluierung
├── email_notifier.py         # E-Mail-Benachrichtigungen für Flugbarkeits-Alerts
├── config.py                 # Konfigurationsdatei
├── requirements.txt          # Python-Abhängigkeiten
├── .env.example              # Beispiel für Umgebungsvariablen
├── data/                     # Datenverzeichnis (wird automatisch erstellt)
│   ├── startplaetze_schweiz.csv  # CSV mit Startplätzen
│   └── wetterdaten.json     # Generierte Wetterdaten
└── README.md                # Diese Datei
```

## Konfiguration

Die Konfiguration befindet sich direkt in den Python-Dateien:

**config.py:**
- `LOCATION`: Standort-Konfiguration (Name, Koordinaten, Windrichtung, etc.)
- `FLIGHT_HOURS_START` / `FLIGHT_HOURS_END`: Flugstunden-Zeitraum (Standard: 9-18 Uhr)
- `FORECAST_DAYS`: Anzahl Tage für Wettervorhersage (Standard: 2)
- `OUTPUT_DIR`: Ausgabeverzeichnis für generierte Dateien

**fetch_weather.py:**
- Aggregiert Wetterdaten von der MeteoSwiss API
- Speichert Daten in `data/wetterdaten.json`
- Sollte vor dem Öffnen des Web-Interfaces ausgeführt werden

## Abhängigkeiten

- `requests>=2.31.0` - HTTP-Requests für API-Zugriff
- `openai>=1.10.0` - OpenAI API Client (für LLM-Evaluierung)
- `python-dotenv>=1.0.0` - Umgebungsvariablen aus .env laden
- `colorama>=0.4.6` - Plattformübergreifende Farbunterstützung für Terminal

## Datenquellen

Das System verwendet die **Open-Meteo API** mit MeteoSwiss ICON CH1 Modellen:
- **API**: [Open-Meteo MeteoSwiss API](https://open-meteo.com/en/docs/meteoswiss-api)
- **Modell**: MeteoSwiss ICON CH1 (1km Auflösung, stündliche Updates)
- **Zeitzone**: Europe/Zurich

## Beispiel-CSV Format

```csv
Fluggebiet,Typ,Platz,Latitude,Longitude,Windrichtung/Ausrichtung,Bemerkung
Zürich,Startplatz,Uetliberg,47.3498,8.4915,Nord-Ost,
Bern,Startplatz,Gurten,46.8200,7.4500,Süd-West,
```

## Web-Interface Details

Das Web-Interface verwendet das "Flyable Window Grid" Design-Konzept:

### Layout-Struktur

- **Header**: Zeigt Standortname, Datum und Tages-Zusammenfassung
- **Zeitachse**: Horizontale Anzeige der Flugstunden (konfigurierbar in `config.py`)
- **4 Datenzeilen**:
  1. **WIND**: Pfeile zeigen Richtung (Norden = oben), Länge/Dicke = Geschwindigkeit, Farbkodierung (Grün/Gelb/Rot)
  2. **NIEDERSCHLAG**: Icons für Regen/Schnee/Gewitter, Intensitäts-Balken, Hintergrundfärbung
  3. **THERMIK**: Vertikaler Balken mit Steigrate, animierte Blasen, Farbverlauf Blau→Orange
  4. **WOLKENBASIS**: Horizontlinie für Startplatzhöhe, Wolken-Icons positioniert relativ zur Basis

### Features

- **High-Contrast Design**: Optimiert für Sonnenlicht am Berg
- **Touch-optimiert**: Funktioniert auf Tablets und Smartphones
- **Detail-Overlay**: Klick/Tap auf eine Zelle zeigt detaillierte Werte
- **Automatisches Laden**: Lädt Daten aus `data/wetterdaten.json`

### Verwendung

1. Wetterdaten aktualisieren: `python fetch_weather.py`
2. `index.html` im Browser öffnen (oder lokalen Webserver verwenden)
3. Nach Daten-Update: Seite im Browser aktualisieren

## Flugbarkeits-Evaluierung Details

### Wetterdaten-Parameter

Die Evaluierung berücksichtigt folgende Parameter:

- **Wind**: Geschwindigkeit, Richtung, Böen, Passung zur erlaubten Startrichtung
- **Thermik**: CAPE-Werte (Convective Available Potential Energy)
  - >500 J/kg = gute Thermik
  - 200-500 J/kg = moderate Thermik
  - <200 J/kg = schwache Thermik
- **Wolkenbasis**: Maximale Flughöhe
- **Bewölkung**: Niedrige, mittlere, hohe Bewölkung
- **Niederschlag**: Regen, Schnee, Wahrscheinlichkeit
- **Sonnenscheindauer**: Für Thermik-Einschätzung

### Evaluierungs-Ergebnis

Das LLM liefert folgende Informationen:

- **flyable**: Ja/Nein Entscheidung
- **rating**: Bewertung von 1-10
- **confidence**: Konfidenz der Bewertung (1-10)
- **conditions**: EXCELLENT | GOOD | MODERATE | POOR | DANGEROUS
- **summary**: Kurze Zusammenfassung (1-2 Sätze)
- **details**: Detaillierte Analyse von Wind, Thermik, Risiken
- **recommendation**: Konkrete Empfehlung für Piloten

### Sicherheits-Fokus

Das System ist konservativ ausgelegt:
- **Bei Zweifel: Nicht fliegbar**
- False Positives werden vermieden (sagt nicht "fliegbar" wenn gefährlich)
- Lokale Besonderheiten werden berücksichtigt (Luftraum, Topografie, Rotoren)

### E-Mail-Benachrichtigungen

Das System kann automatisch E-Mail-Benachrichtigungen senden, wenn die Flugbarkeits-Konditionen **EXCELLENT** oder **GOOD** sind:

- **Automatischer Versand**: Bei jeder Analyse wird geprüft, ob die Konditionen EXCELLENT oder GOOD sind
- **E-Mail-Inhalt**: Enthält alle wichtigen Informationen (Bewertung, Zusammenfassung, Details zu Wind/Thermik/Risiken, Empfehlung)
- **Konfiguration**: Über Umgebungsvariablen in der `.env` Datei (siehe Abschnitt 4.1)
- **Optional**: Wenn nicht konfiguriert, läuft das System normal weiter ohne E-Mails zu senden
- **Fehlerbehandlung**: E-Mail-Fehler stoppen die Analyse nicht

## Fehlerbehandlung

Das System enthält Fehlerbehandlung für:
- Netzwerkfehler und Timeouts
- Fehlende oder ungültige Daten
- API-Fehler (mit Retry-Logic und exponential backoff)
- Dateisystem-Fehler
- OpenAI API Rate Limits
- Ungültige LLM-Antworten (mit Fallback)

## Lizenz

Dieses Projekt ist für den persönlichen und kommerziellen Gebrauch frei verfügbar.
