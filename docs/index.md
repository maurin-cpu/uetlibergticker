# Uetliberg Ticker
Willkommen zur Dokumentation des **Uetliberg Tickers**!

Diese Anwendung ist ein leistungsfähiges Dashboard und Prognosetool für Gleitschirmpiloten in der Schweiz. Sie bewertet stündlich das Thermik-Gütelogik-Rating und andere meteorologische Parameter für 24 verschiedene Thermikregionen.

## Kernfunktionen
- **Thermik-Berechnung:** Physikalisch fundierte Simulation des Paketaufstiegs basierend auf Temperatur, Feuchte und Sonneneinstrahlung.
- **Wetter-Zeitlinien:** Interaktive D3.js Diagramme, um den Tagesverlauf von Wind, Thermik und Wolkenbasis auf einen Blick zu erfassen.
- **Föhn & Bise Warnungen:** Analyse von Druckgradienten und Höhenwind für Sicherheitswarnungen.
- **Regionale Detailauswertung:** Übersichtskarte und detaillierte Meteogramme für jede Flugregion.

## Quickstart
Um das Tool lokal zu starten:
```bash
npm run dev
```
Das Dashboard ist unter `http://127.0.0.1:5000` erreichbar.

## Navigation in dieser Doku
- Unter **Architektur** findest du Informationen zum technischen Aufbau der Applikation (Flask, API-Anbindung, InstantDB).
- Unter **Meteorologie** wird im Detail erklärt, wie die Thermik und andere flugrelevante Parameter berechnet werden.
