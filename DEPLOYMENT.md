# Vercel Deployment Anleitung

## Übersicht

Dieses Projekt wird auf Vercel als Serverless Function deployed und führt täglich um 05:00 UTC einen Cron-Job aus, der:
1. Wetterdaten abruft (`fetch_weather.py`)
2. LLM-Analyse durchführt (`location_evaluator.py`)
3. E-Mail-Benachrichtigungen sendet (`email_notifier.py`)

## GitHub Repository

Das Projekt befindet sich auf: https://github.com/maurin-cpu/uetlibergticker.git

## Deployment-Schritte

### 1. Vercel mit GitHub verbinden

1. Gehe zu [Vercel Dashboard](https://vercel.com/dashboard)
2. Klicke auf "New Project"
3. Wähle "Import Git Repository"
4. Wähle das Repository `maurin-cpu/uetlibergticker` aus
5. Vercel erkennt automatisch das Python-Projekt

### 2. Environment Variables konfigurieren

In den Vercel-Projekteinstellungen unter "Environment Variables" folgende Variablen hinzufügen:

**Erforderlich:**
- `OPENAI_API_KEY` - Dein OpenAI API Key
- `EMAIL_SMTP_SERVER` - SMTP-Server (z.B. `smtp.gmail.com`)
- `EMAIL_SMTP_PORT` - SMTP-Port (z.B. `587` für TLS)
- `EMAIL_SENDER` - Absender-E-Mail-Adresse
- `EMAIL_PASSWORD` - E-Mail-Passwort oder App-Passwort
- `EMAIL_RECIPIENT` - Empfänger-E-Mail-Adresse

**Optional:**
- `OPENAI_MODEL` - OpenAI Modell (Standard: `gpt-4`)

### 3. Deployment

Nach dem ersten Import deployt Vercel automatisch. Bei jedem Push zu GitHub wird automatisch neu deployed.

### 4. Cron-Job aktivieren

Der Cron-Job ist bereits in `vercel.json` konfiguriert:
- **Zeitplan**: Täglich um 05:00 UTC (`0 5 * * *`)
- **Route**: `/api/cron`
- **Zeitzone**: UTC (entspricht 06:00 MEZ im Winter, 07:00 MESZ im Sommer)

Der Cron-Job wird automatisch aktiviert nach dem ersten Deployment.

## Manuelles Testen

Du kannst die Cron-Function manuell testen, indem du die URL aufrufst:
```
https://deine-domain.vercel.app/api/cron
```

**Wichtig**: Für Produktionsumgebungen sollte ein `CRON_SECRET` hinzugefügt werden, um unbefugte Zugriffe zu verhindern.

## Projektstruktur

```
uetliberg_ticker/
├── api/
│   └── cron.py              # Serverless Function für Cron-Job
├── vercel.json              # Vercel-Konfiguration mit Cron-Job
├── fetch_weather.py         # Wetterdaten-Abruf
├── location_evaluator.py    # LLM-Analyse
├── email_notifier.py        # E-Mail-Versand
├── config.py                # Konfiguration
└── requirements.txt         # Python-Dependencies
```

## E-Mail-Format

Die E-Mails werden im HTML-Format versendet und enthalten:
- Zusammenfassung (Summary)
- Bewertung (Rating) und Konfidenz (Confidence)
- Konditionen (Conditions)
- Wind-Analyse (Details)
- Thermik-Analyse (Details)
- Risiko-Analyse (Details)
- Empfehlung (Recommendation)

E-Mails werden **immer** gesendet, unabhängig von den Wetterbedingungen.

## Troubleshooting

### Cron-Job läuft nicht
- Prüfe ob das Projekt in der Produktionsumgebung deployed ist
- Cron-Jobs laufen nur in Production, nicht in Preview/Development
- Prüfe die Vercel-Logs unter "Functions" → "cron"

### E-Mails werden nicht gesendet
- Prüfe die Environment Variables in Vercel
- Prüfe die Vercel-Logs für Fehlermeldungen
- Stelle sicher, dass `EMAIL_PASSWORD` ein App-Passwort ist (bei Gmail)

### Wetterdaten werden nicht abgerufen
- Prüfe die Vercel-Logs
- Stelle sicher, dass die Open-Meteo API erreichbar ist
- Prüfe ob `/tmp` Verzeichnis verfügbar ist (automatisch bei Vercel)

## Weitere Informationen

- [Vercel Cron Jobs Dokumentation](https://vercel.com/docs/cron-jobs)
- [Vercel Python Functions](https://vercel.com/docs/functions/runtimes/python)

