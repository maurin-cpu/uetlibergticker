# Vercel Deployment Setup für Uetliberg Ticker

## Problem-Diagnose

### Identifizierte Probleme:
1. **Wetteranalyse-Box ist leer**: Daten werden nicht korrekt auf Vercel gespeichert/geladen
2. **Keine E-Mails werden versendet**: Environment Variables fehlen in Vercel
3. **Cron-Job läuft nur 1x täglich**: Aktuell um 5:00 Uhr morgens

## Lösung

### 1. Vercel Environment Variables setzen

Gehe zu deinem Vercel Dashboard → Projekt → Settings → Environment Variables und füge folgende Variablen hinzu:

**KRITISCH - Ohne diese funktioniert die App NICHT:**

```bash
# OpenAI API Konfiguration (erforderlich für LLM-Analyse)
OPENAI_API_KEY=dein-openai-api-key-hier  # Erstelle einen API Key auf https://platform.openai.com/api-keys
OPENAI_MODEL=gpt-4

# E-Mail-Benachrichtigungen (erforderlich für E-Mail-Versand)
EMAIL_SMTP_SERVER=smtp.gmail.com
EMAIL_SMTP_PORT=587
EMAIL_SENDER=deine-email@gmail.com  # Gmail-Adresse für den Versand
EMAIL_PASSWORD=dein-app-passwort-hier  # Gmail App-Passwort (nicht dein normales Passwort!)
EMAIL_RECIPIENT=mutschgito@hotmail.com  # WICHTIG: Diese E-Mail-Adresse erhält alle Benachrichtigungen
```

**WICHTIG:**
- Stelle sicher, dass alle Variablen für **Production**, **Preview** und **Development** gesetzt sind
- Nach dem Hinzufügen musst du die App neu deployen

### 2. ⚠️ WICHTIG: Datenpersistenz-Problem auf Vercel

**KRITISCHES PROBLEM:** `/tmp` auf Vercel ist **NICHT persistent** - Dateien gehen bei jedem Neustart verloren!

**Auswirkungen:**
- `wetterdaten.json` und `evaluations.json` werden in `/tmp` gespeichert
- Bei jedem Neustart der Function gehen die Daten verloren
- Die Wetteranalyse-Box im Web-Interface bleibt leer, wenn keine Daten vorhanden sind
- Der Cron-Job muss regelmäßig laufen, um Daten neu zu generieren

**Workaround (aktuell implementiert):**
- Der `/api/auto-email` Endpunkt führt automatisch den Cron-Job aus, wenn keine Daten vorhanden sind
- Dies kann zu Timeouts führen, wenn zu viele Requests gleichzeitig kommen
- **EMPFOHLEN:** Verwende einen externen Cron-Service (siehe unten), der regelmäßig Daten generiert

**LANGZEIT-LÖSUNG:** Verwende Vercel Blob Storage oder KV für persistente Daten

#### Option A: Vercel Blob Storage (EINFACHSTE LÖSUNG, aber kostenpflichtig)
1. Gehe zu Vercel Dashboard → Storage → Create Database → Blob
2. Installiere `@vercel/blob` in `requirements.txt`
3. Verwende Blob Storage für `wetterdaten.json` und `evaluations.json`
4. **Kosten:** Ab $20/Monat für Vercel Pro Plan

#### Option B: Externe Datenbank (KOSTENLOS)
- **Supabase** (kostenlos, empfohlen): PostgreSQL-Datenbank mit REST API
- **PlanetScale** (kostenlos): MySQL-kompatible Datenbank
- **MongoDB Atlas** (kostenlos): NoSQL-Datenbank

#### Option C: Regelmäßiger Cron-Job (AKTUELLER WORKAROUND)
- Verwende einen externen Cron-Service (cron-job.org, EasyCron, GitHub Actions)
- Der Cron-Job ruft `/api/cron` regelmäßig auf (z.B. alle 6 Stunden)
- Dies generiert neue Daten und speichert sie in `/tmp`
- **Nachteil:** Daten gehen bei Neustart verloren, müssen regelmäßig neu generiert werden

### 3. Cron Job für 10-Minuten-Intervall konfiguriert

Die `vercel.json` wurde aktualisiert auf **alle 10 Minuten** für automatische E-Mails.

**NEUER ENDPUNKT:** `/api/auto-email`
- Dieser Endpunkt wird alle 10 Minuten aufgerufen
- Sendet automatisch E-Mails basierend auf den neuesten Wetterdaten
- Falls keine Daten vorhanden sind, führt er zuerst den Cron-Job aus

**WICHTIG - VERCEL FREE PLAN LIMITIERUNG:**
- ⚠️ Vercel Cron Jobs auf Hobby-Plan (Free) sind limitiert auf **1x/Tag**
- ⚠️ Der 10-Minuten-Cron wird NICHT auf Free Plan funktionieren!
- ✅ Für 10-Minuten-Intervalle benötigst du **Vercel Pro Plan** ($20/Monat)
- ✅ **EMPFOHLEN:** Verwende einen externen Cron-Service (kostenlos - siehe unten)

### 4. Alternative: Externe Cron Services (KOSTENLOS)

Falls du keinen Pro Plan hast, verwende einen dieser Services:

#### cron-job.org (KOSTENLOS, EMPFOHLEN)
1. Registriere dich auf https://cron-job.org
2. Erstelle einen neuen Cron Job:
   - **URL:** `https://deine-app.vercel.app/api/auto-email` (WICHTIG: Verwende /api/auto-email, nicht /api/cron!)
   - **Intervall:** Alle 10 Minuten (`*/10 * * * *`)
   - **Zeitzone:** Europe/Zurich
   - **Methode:** GET

#### EasyCron (KOSTENLOS)
1. Registriere dich auf https://www.easycron.com
2. Erstelle Cron Job:
   - **URL:** `https://deine-app.vercel.app/api/auto-email`
   - **Cron Expression:** `*/10 * * * *` (alle 10 Minuten)

#### GitHub Actions (KOSTENLOS)

**VORBEREITUNG - GitHub Secrets konfigurieren:**

1. Gehe zu deinem GitHub Repository → Settings → Secrets and variables → Actions
2. Klicke auf "New repository secret"
3. Erstelle ein Secret namens `VERCEL_URL` mit dem Wert deiner Vercel App URL (z.B. `https://deine-app.vercel.app`)

**Workflow-Datei:** `.github/workflows/auto-email.yml` (bereits erstellt)

Der Workflow wird automatisch alle 10 Minuten ausgeführt und ruft den `/api/auto-email` Endpunkt auf.

**WICHTIG:** Stelle sicher, dass das `VERCEL_URL` Secret in GitHub gesetzt ist, sonst schlägt der Workflow fehl!

## Deployment-Checklist

- [ ] Environment Variables in Vercel gesetzt
- [ ] App neu deployed
- [ ] Cron Job konfiguriert (Vercel Pro ODER externer Service)
- [ ] Blob Storage konfiguriert (für persistente Daten)
- [ ] Test-E-Mail über Web-Interface gesendet
- [ ] Cron Job manuell getestet via `https://deine-app.vercel.app/api/cron`

## Debugging

### Prüfe ob Environment Variables korrekt gesetzt sind:
```bash
curl https://deine-app.vercel.app/api/email-config
```

### Teste E-Mail-Versand manuell:
```bash
curl -X POST https://deine-app.vercel.app/api/test-email
```

### Teste automatischen E-Mail-Versand:
```bash
curl https://deine-app.vercel.app/api/auto-email
```

### Teste Cron Job manuell (Wetterdaten + Analyse):
```bash
curl https://deine-app.vercel.app/api/cron
```

### Prüfe Logs in Vercel:
1. Gehe zu Vercel Dashboard → Projekt → Deployments
2. Klicke auf neuestes Deployment
3. Gehe zu "Functions" → Wähle deine Funktion → Siehe Logs

## Hinweise

### ⚠️ KRITISCH: Datenpersistenz auf Vercel

**Problem:** `/tmp` auf Vercel ist **NICHT persistent**!

- Dateien in `/tmp` gehen bei jedem Neustart der Function verloren
- Dies betrifft sowohl `wetterdaten.json` als auch `evaluations.json`
- Die Wetteranalyse-Box bleibt leer, wenn keine Daten vorhanden sind

**Aktueller Workaround:**
- Der `/api/auto-email` Endpunkt führt automatisch `/api/cron` aus, wenn keine Daten vorhanden sind
- Dies generiert neue Daten, aber sie gehen beim nächsten Neustart wieder verloren
- **Lösung:** Verwende einen externen Cron-Service, der regelmäßig `/api/cron` aufruft (z.B. alle 6 Stunden)

**Langzeit-Lösungen:**
1. **Vercel Blob Storage** (kostenpflichtig, ab $20/Monat)
2. **Externe Datenbank** (kostenlos: Supabase, PlanetScale, MongoDB Atlas)
3. **Regelmäßiger Cron-Job** (kostenlos: cron-job.org, EasyCron, GitHub Actions)

### Vercel Free Plan Limitierungen

1. **Cron Jobs:** Nur 1x/Tag (nicht für 10-Minuten-Intervalle geeignet)
2. **Function Timeout:** 10 Sekunden (kann bei LLM-Analysen problematisch sein)
3. **Keine persistente Dateien:** `/tmp` wird bei jedem Neustart geleert
4. **Function Execution Time:** Limitiert auf 10 Sekunden

### Empfohlene Upgrades

- **Vercel Pro** ($20/Monat): 
  - Häufigere Cron Jobs (alle 10 Minuten möglich)
  - Längere Function Timeouts
  - Blob Storage für persistente Daten

### Kostenlose Alternativen

- **Externe Cron Services:** cron-job.org, EasyCron (für regelmäßige Daten-Generierung)
- **GitHub Actions:** Für automatische Cron-Jobs (siehe oben)
- **Externe Datenbank:** Supabase, PlanetScale, MongoDB Atlas (für persistente Datenspeicherung)
