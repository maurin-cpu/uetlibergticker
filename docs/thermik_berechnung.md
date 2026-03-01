# Thermik-Berechnung im Uetliberg Ticker

## Überblick

Der Uetliberg Ticker berechnet für 24 Schweizer Thermikregionen ein stündliches **Thermik-Güte-Rating** (0–10). Die Berechnung simuliert physikalisch den Aufstieg eines Luftpakets vom Boden durch die Atmosphäre und leitet daraus erwartetes Steigen (m/s) und nutzbare Arbeitshöhe ab.

```
Wetterdaten (Open-Meteo API)
        │
        ▼
┌─────────────────────────┐
│  Bodentemperatur + Sonne │──▶ Auslösetemperatur
│  Taupunkt                │──▶ LCL (Wolkenbasis)
│  Höhenprofile (hPa)      │──▶ Paketaufstieg
│  Grenzschichthöhe        │──▶ Höhenbegrenzung
└─────────────────────────┘
        │
        ▼
┌─────────────────────────┐
│  Thermal Index Profil    │
│  w* Steigrate            │
│  Güte-Rating (0-10)      │
└─────────────────────────┘
```

---

## 1. Eingangsdaten

Pro Region und Stunde werden folgende Werte von der **Open-Meteo API** (Modell: `icon_seamless`) bezogen:

| Parameter | Beschreibung |
|---|---|
| `temperature_2m` | Bodentemperatur in 2m Höhe (°C) |
| `dewpoint_2m` / `relative_humidity_2m` | Taupunkt oder relative Feuchte am Boden |
| `boundary_layer_height` | Grenzschichthöhe über Grund (m AGL) |
| `sunshine_duration` | Sonnenscheindauer in der Stunde (Sekunden, max 3600) |
| `cape` | Convective Available Potential Energy (J/kg) |
| `geopotential_height_{X}hPa` | Geopotentielle Höhe auf Druckniveau X (m MSL) |
| `temperature_{X}hPa` | Temperatur auf Druckniveau X (°C) |

**Druckniveaus:** 1000, 975, 950, 925, 900, 875, 850, 825, 800, 775, 750, 700, 600 hPa

Diese Niveaus decken den Bereich von ca. 0 m bis 4000 m MSL ab, in Schritten von ~200–250 m.

---

## 2. Taupunkt-Berechnung

Falls kein direkter Taupunkt geliefert wird, erfolgt die Berechnung über die **Magnus-Formel**:

```
α = ln(RH/100) + (A · T) / (B + T)
Td = (B · α) / (A - α)
```

Konstanten: `A = 17.625`, `B = 243.04`

---

## 3. Auslösetemperatur (Trigger Temperature)

Die Sonne erwärmt den Boden stärker als die freie Atmosphäre. Das Modell addiert einen **Sonnenschein-Bonus** auf die Bodentemperatur:

```
sun_factor = min(1.0, sunshine_duration / 3600)
T_trigger  = T_surface + 2.0 · sun_factor
```

- Bei voller Sonne (3600s): +2.0 °C Überhitzung
- Bei bedecktem Himmel (0s): +0.0 °C
- Teilverhältnisse linear interpoliert

---

## 4. LCL – Wolkenbasis (Lifting Condensation Level)

Die Höhe, ab der das aufsteigende Luftpaket kondensiert (Wolkenbildung), wird mit der **Spread-Faustregel** berechnet:

```
Spread  = T_trigger - T_dewpoint
LCL_AGL = Spread · 125 m/°C
LCL_MSL = Elevation + LCL_AGL
```

Ein Spread von 10 °C ergibt eine Wolkenbasis von 1250 m über Grund.

---

## 5. Paketaufstieg – Thermal Index Profil

Der Kern der Berechnung: Ein virtuelles Luftpaket steigt vom Boden auf und wird mit dem realen Höhenprofil verglichen.

### Trockenadiabatischer Aufstieg (unter LCL)

```
T_parcel(h) = T_trigger - 0.0098 · (h - elevation)
```

Das Paket kühlt mit dem **DALR** (Dry Adiabatic Lapse Rate) von **9.8 °C/km** ab.

### Feuchtadiabatischer Aufstieg (über LCL)

Über dem LCL wird Kondensationswärme frei. Die Abkühlung verlangsamt sich auf den **SALR** (Saturated Adiabatic Lapse Rate) von ca. **6.0 °C/km**:

```
T_parcel(h) = T_trigger - 0.0098 · (LCL - elevation) - 0.006 · (h - LCL)
```

### Thermal Index (TI)

Auf jeder Höhenschicht wird der TI berechnet:

```
TI = T_environment - T_parcel
```

| TI | Bedeutung |
|---|---|
| TI < 0 | Paket ist **wärmer** als Umgebung → **Steigen** |
| TI = 0 | Gleichgewicht (Thermik-Obergrenze) |
| TI > 0 | Paket ist **kälter** → Sinken, Inversion |

### Aufstiegs-Abbruch

Das Paket steigt, solange es mindestens gleich warm oder nur 0.5 °C kälter ist als die Umgebung (Trägheitstoleranz für eine reale Thermikblase):

```
Abbruch wenn: T_parcel < T_environment - 0.5
```

Die letzte Höhe, auf der das Paket noch steigt, definiert die **maximale Thermikhöhe**.

---

## 6. Grenzschicht-Begrenzung

Die Grenzschichthöhe (Boundary Layer Height) begrenzt die Thermik zusätzlich:

```
BLH_MSL = Elevation + BLH_AGL

Wenn max_thermal_height > BLH_MSL:
    max_thermal_height = BLH_MSL
```

Die Grenzschicht ist die turbulente, durchmischte Schicht über dem Boden. Thermik durchstösst selten deren Obergrenze.

---

## 7. Steigrate w* (Convective Velocity Scale)

Aus der mittleren Temperaturdifferenz und der Thermiktiefe wird die **konvektive Geschwindigkeitsskala** abgeleitet:

```
mean_dT       = Σ(T_parcel - T_env) / Anzahl_Schichten
thermal_depth = max_thermal_height - elevation
T_kelvin      = T_surface + 273.15

raw_w*  = √( g/T_kelvin · mean_dT · thermal_depth )
```

Dabei ist `g = 9.81 m/s²`.

### Kalibrierung auf Gleitschirm-Variowerte

Das physikalische w* gibt die Geschwindigkeit der Luftmassenkonvektion an. Ein Gleitschirmpilot im Bart erlebt weniger:

```
climb_rate = raw_w* · 0.3 · sun_factor
```

- Faktor **0.3**: Empirische Kalibrierung (Paketmitte steigt schneller als der Schirm, Abwind am Rand, etc.)
- **sun_factor**: Reduziert Steigen proportional zur tatsächlichen Sonnenscheindauer
- Maximum: **6.0 m/s** (Obergrenze für Alpen-Thermik)

### Mindesthöhe

Ist die nutzbare Thermikhöhe weniger als 300 m über Grund, wird die Thermik als **nicht nutzbar** gewertet:

```
Wenn max_thermal_height < elevation + 300m:
    rating = 1, climb_rate = 0.0
```

---

## 8. Güte-Rating (0–10)

Das stündliche Rating leitet sich direkt aus der Steigrate ab:

| Steigen (m/s) | Rating | Einordnung |
|---|---|---|
| < 0.5 | 0 | Keine Thermik |
| 0.5 – 1.2 | 3 | Schwache Thermik |
| 1.2 – 2.0 | 5 | Moderate Thermik |
| 2.0 – 3.5 | 8 | Gute bis starke Thermik |
| > 3.5 | 10 | Sehr starke Thermik |

---

## 9. Tages-Aggregation

Für die Landkarte werden die stündlichen Werte (Flugstunden 09:00–18:00) zu einem **Tageswert pro Region** verdichtet:

| Tageswert | Aggregation |
|---|---|
| `climb_rate` | Maximum aller Stundenwerte |
| `rating` | Mittelwert der besten 3 Stunden |
| `max_height` | Maximum aller Stundenwerte |
| `lcl` | Durchschnitt aller Stunden mit LCL > 0 |
| `cape` | Maximum aller Stundenwerte |

Die **Top-3-Regel** beim Rating verhindert, dass eine einzelne gute Stunde den Tageswert dominiert, erlaubt aber dennoch gute Wertungen wenn das Thermiknachmittags-Fenster kurz ist.

---

## 10. Datenfluss-Architektur

```
config.py (24 Regionen mit Zentroid lat/lon)
     │
     ▼
fetch_regions.py
     │
     ├── Open-Meteo API (icon_seamless, 3 Tage, alle Regionen in einem Request)
     │
     ├── thermik_calculator.py (pro Stunde pro Region)
     │       ├── Taupunkt (Magnus)
     │       ├── LCL (Spread · 125)
     │       ├── Paketaufstieg (DALR/SALR vs. Höhenprofil)
     │       ├── w* → climb_rate
     │       └── Rating (0-10)
     │
     └── Tages-Aggregation
            │
            ▼
     data/regions_forecast.json
            │
            ▼
     web.py → /api/regions-data
            │
            ▼
     templates/regions.html (Leaflet-Karte mit Rating-Polygonen)
```

---

## Physikalische Konstanten

| Konstante | Wert | Beschreibung |
|---|---|---|
| g | 9.81 m/s² | Erdbeschleunigung |
| cp | 1005 J/(kg·K) | Spezifische Wärmekapazität trockener Luft |
| R_d | 287.05 J/(kg·K) | Gaskonstante trockene Luft |
| L_v | 2.5 × 10⁶ J/kg | Verdampfungswärme Wasser |
| DALR | 9.8 °C/km | Trockenadiabatischer Gradient |
| SALR | ~6.0 °C/km | Feuchtadiabatischer Gradient (vereinfacht) |

---

## Quellen und Referenzen

- **Deardorff (1970)**: Convective velocity scale w* — Grundlage der Steigrate-Berechnung
- **Magnus-Formel**: Standard-Approximation für Sättigungsdampfdruck → Taupunkt
- **LCL-Approximation**: Eaton (1917), Spread × 125 m/°C — bewährte Piloten-Faustregel
- **Open-Meteo API**: Wetterdaten-Quelle, Modell ICON (DWD) seamless
- **swissBOUNDARIES3D**: Grundlage der 24 Thermikregionen-Polygone (Swisstopo)
