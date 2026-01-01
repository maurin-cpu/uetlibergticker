# MeteoSwiss Wetterdaten Aggregator

Python-Skript zur Aggregation von Wetterdaten für die Schweiz. Das Skript ruft Wetterdaten von MeteoSwiss Open Data ab, speichert sie als CSV-Datei und zeigt sie im Terminal an.

## Schnellstart

1. **Virtuelle Umgebung erstellen (empfohlen):**
   ```bash
   python -m venv .venv
   ```

2. **Virtuelle Umgebung aktivieren:**
   - **Windows (PowerShell):**
     ```powershell
     .venv\Scripts\Activate.ps1
     ```
   - **Windows (CMD):**
     ```cmd
     .venv\Scripts\activate.bat
     ```
   - **Linux/Mac:**
     ```bash
     source .venv/bin/activate
     ```

3. **Abhängigkeiten installieren:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Programm starten:**
   ```bash
   python weather_aggregator.py
   ```

Das Programm ruft automatisch Wetterdaten ab, speichert sie in `data/wetterdaten.csv` und zeigt eine Übersicht im Terminal an.

**Hinweis:** Stellen Sie sicher, dass die virtuelle Umgebung aktiviert ist, bevor Sie das Programm starten.

## Funktionen

Das Skript sammelt folgende Wetterdaten:
- **Windrichtung** (in Grad)
- **Windstärke** (in m/s oder km/h)
- **Temperatur** (in °C)
- **Höhe der Bewölkung** (in Metern)

## Voraussetzungen

- **Python 3.7 oder höher** (prüfen mit `python --version`)
- **Internetverbindung** für API-Zugriff
- **pip** (Python Package Manager)

## Installation

### Schritt 1: Python prüfen

Stellen Sie sicher, dass Python 3.7 oder höher installiert ist:
```bash
python --version
```

### Schritt 2: Virtuelle Umgebung erstellen (empfohlen)

Eine virtuelle Umgebung isoliert die Projektabhängigkeiten:

```bash
python -m venv .venv
```

### Schritt 3: Virtuelle Umgebung aktivieren

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

Nach der Aktivierung sollte `(.venv)` am Anfang Ihrer Eingabeaufforderung erscheinen.

### Schritt 4: Abhängigkeiten installieren

Installieren Sie die erforderlichen Python-Pakete:
```bash
pip install -r requirements.txt
```

Die Installation umfasst:
- `pandas` (>=2.0.0) - Datenverarbeitung und CSV-Export
- `requests` (>=2.31.0) - HTTP-Requests für API-Zugriff

**Hinweis:** Wenn Sie keine virtuelle Umgebung verwenden möchten, können Sie die Pakete auch global installieren, dies wird jedoch nicht empfohlen.

## Verwendung

### Programm starten

**Wichtig:** Stellen Sie sicher, dass die virtuelle Umgebung aktiviert ist!

Führen Sie das Skript direkt über das Terminal aus:

```bash
python weather_aggregator.py
```

**Hinweise:**
- Stellen Sie sicher, dass Sie sich im Projektverzeichnis befinden
- Die virtuelle Umgebung muss aktiviert sein (Sie sollten `(.venv)` in der Eingabeaufforderung sehen)

Das Skript führt automatisch folgende Schritte aus:
1. Ruft Wetterdaten für die letzten 7 Tage ab
2. Aggregiert Daten von mehreren Schweizer Wetterstationen
3. Speichert die Daten als CSV in `data/wetterdaten.csv`
4. Zeigt eine Übersicht im Terminal an

### Konfiguration

Sie können die Konfiguration in `config.py` anpassen:

- **Stationen**: Bearbeiten Sie `WEATHER_STATIONS` um andere Stationen hinzuzufügen
- **Zeitraum**: Ändern Sie `DEFAULT_DAYS_BACK` um einen anderen Standard-Zeitraum zu setzen
- **Ausgabepfad**: Passen Sie `OUTPUT_DIR` und `OUTPUT_FILENAME` an

### Verfügbare Standorte

Standardmäßig werden folgende Schweizer Standorte verwendet:
- Zürich
- Bern
- Genf
- Basel
- Lausanne
- Luzern
- St. Gallen
- Lugano
- Sion
- Chur
- Payerne
- Samedan

Die Standorte können in `config.py` angepasst werden.

## Ausgabe

### CSV-Datei

Die Daten werden als CSV-Datei mit folgenden Spalten gespeichert:
- `station` - Name der Wetterstation
- `station_code` - Code der Station
- `datum` - Datum und Uhrzeit der Messung
- `temperatur` - Temperatur in °C
- `windrichtung` - Windrichtung in Grad
- `windstaerke` - Windstärke in m/s oder km/h
- `bewoelkungshoehe` - Höhe der Bewölkung in Metern
- `latitude` - Geografische Breite
- `longitude` - Geografische Länge

### Terminal-Ausgabe

Das Skript zeigt im Terminal:
- Anzahl der abgerufenen Datensätze
- Anzahl der Stationen
- Zeitraum der Daten
- Detaillierte Tabelle mit den ersten 20 Datensätzen
- Statistiken (Mittelwert, Min, Max) für alle numerischen Werte

## Datenquellen

Das Skript verwendet die **Open-Meteo API** mit MeteoSwiss ICON CH1 Modellen:
- **API**: [Open-Meteo MeteoSwiss API](https://open-meteo.com/en/docs/meteoswiss-api)
- **Modell**: MeteoSwiss ICON CH1 (1km Auflösung, stündliche Updates)
- **Datenbereich**: Schweiz mit 12 wichtigen Standorten

Die Daten werden direkt von MeteoSwiss Wettermodellen abgerufen und bieten hochauflösende Vorhersagen für die Schweiz.

## Fehlerbehandlung

Das Skript enthält umfassende Fehlerbehandlung für:
- Netzwerkfehler und Timeouts
- Fehlende oder ungültige Daten
- API-Fehler (Rate Limits, HTTP-Fehler)
- Dateisystem-Fehler

Bei Problemen zeigt das Skript hilfreiche Fehlermeldungen und Lösungsvorschläge.

## Beispiel-Ausgabe

```
============================================================
MeteoSwiss Wetterdaten Aggregator
============================================================
Zeitraum: 2024-12-23 bis 2024-12-30
Standorte: Zürich, Bern, Genf, Basel, Lausanne... (12 insgesamt)
============================================================

Rufe Daten über Open-Meteo API (MeteoSwiss ICON CH) ab...
  ✓ Zürich: 168 Stunden-Datensätze
  ✓ Bern: 168 Stunden-Datensätze
  ✓ Genf: 168 Stunden-Datensätze
  ...

✓ Insgesamt 2016 Datensätze über Open-Meteo API abgerufen

✓ Daten gespeichert: data/wetterdaten.csv
  (150 Datensätze, 45230 Bytes)

============================================================
WETTERDATEN ÜBERSICHT
============================================================

Anzahl Datensätze: 150
Stationen: 10
Zeitraum: 2024-12-23 00:00:00 bis 2024-12-30 23:00:00

[... detaillierte Tabelle ...]
```

## Lizenz

Dieses Projekt ist für den persönlichen und kommerziellen Gebrauch frei verfügbar.

## Weitere Informationen

- [MeteoSwiss Open Data Dokumentation](https://opendatadocs.meteoswiss.ch/)
- [mch-extract auf PyPI](https://pypi.org/project/mch-extract/)

## Support & Troubleshooting

### Häufige Probleme

**Problem: `python: command not found` oder `python: Der Befehl wurde nicht gefunden`**
- Lösung: Verwenden Sie `python3` statt `python`, oder stellen Sie sicher, dass Python installiert ist
- Windows: Prüfen Sie, ob Python im PATH enthalten ist

**Problem: `ModuleNotFoundError` oder `No module named 'pandas'`**
- Lösung: Stellen Sie sicher, dass die virtuelle Umgebung aktiviert ist
- Installieren Sie die Abhängigkeiten mit `pip install -r requirements.txt`
- Falls das nicht funktioniert, versuchen Sie `pip3 install -r requirements.txt`
- Prüfen Sie, ob die Pakete installiert sind: `pip list`

**Problem: Netzwerkfehler oder Timeout**
- Lösung: Prüfen Sie Ihre Internetverbindung
- Die API benötigt eine aktive Internetverbindung

**Problem: `PermissionError` beim Speichern der CSV-Datei**
- Lösung: Stellen Sie sicher, dass Sie Schreibrechte im Projektverzeichnis haben
- Das `data/` Verzeichnis wird automatisch erstellt

### Weitere Hilfe

Bei anderen Problemen oder Fragen:
1. Prüfen Sie Ihre Internetverbindung
2. Stellen Sie sicher, dass alle Abhängigkeiten installiert sind (`pip list`)
3. Überprüfen Sie die Konfiguration in `config.py`
4. Beachten Sie, dass Open-Meteo maximal 16 Tage Vorhersage unterstützt
5. Prüfen Sie die Python-Version: `python --version` (benötigt 3.7+)

## Technische Details

- **API-Endpoint**: `https://api.open-meteo.com/v1/forecast`
- **Modell**: `meteoswiss_icon_ch1` (1km räumliche Auflösung)
- **Zeitauflösung**: Stündlich
- **Vorhersagedauer**: Bis zu 16 Tage
- **Zeitzone**: Europe/Zurich

