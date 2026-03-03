#!/usr/bin/env python3
"""
Föhn-Indikatoren für Gleitschirmflieger.

Berechnet Föhn-Warnstufen basierend auf:
- Druckgradient (Delta-P) Nord vs. Süd der Alpen
- Höhenwind am Alpenhauptkamm (700 hPa ≈ 3000 m)
- Lokale Luftfeuchtigkeit (Föhnluft ist trocken)
- Böigkeit (starke Differenz Wind/Böen = turbulent)

Verwendet MeteoSwiss ICON für die Schweiz (hochauflösend).
"""

import requests
from datetime import datetime
from typing import Optional

import config

# ============================================================================
# FÖHN-REFERENZSTATIONEN
# ============================================================================
# Südföhn: Hoher Druck im Süden (Lugano), tiefer Druck im Norden (Zürich)
# Delta-P = P_süd - P_nord > 0 → Südföhn-Gefahr

FOEHN_STATIONS = {
    "nord": {
        "name": "Zürich",
        "lat": 47.37,
        "lon": 8.55,
        "role": "Nordseite (Lee)",
    },
    "sued": {
        "name": "Lugano",
        "lat": 46.0,
        "lon": 8.96,
        "role": "Südseite (Luv)",
    },
}

# Südföhn: Wind am Kamm aus S/SW (135°–225°)
SUEDFOEHN_DIR_START = 135
SUEDFOEHN_DIR_END = 225

# Schwellenwerte (Gemini-Empfehlung)
THRESHOLD_DELTA_P_CAUTION = 4   # hPa – Vorsicht
THRESHOLD_DELTA_P_DANGER = 8    # hPa – Flugverbot-Empfehlung
THRESHOLD_CREST_WIND_CAUTION = 54   # km/h (15 m/s) – starkes Warnsignal
THRESHOLD_CREST_WIND_DANGER = 180   # km/h (50 m/s) – Flugverbot
THRESHOLD_HUMIDITY_LOW = 40     # % – Föhn „durchgebrochen“
THRESHOLD_GUST_RATIO = 1.5      # Böen/Wind > 1.5 = böig/turbulent


def _potential_temperature(temp_kelvin: float, pressure_hpa: float, p0: float = 1000.0) -> float:
    """Potenzielle Temperatur θ = T * (P0/P)^0.2854"""
    if pressure_hpa <= 0:
        return 0.0
    return temp_kelvin * (p0 / pressure_hpa) ** 0.2854


def fetch_foehn_data(forecast_days: int = 2) -> Optional[dict]:
    """
    Holt Föhn-relevante Daten von Open-Meteo (MeteoSwiss ICON).

    Multi-Point-Abfrage: Nord (Zürich) + Süd (Lugano).
    """
    lats = [FOEHN_STATIONS["nord"]["lat"], FOEHN_STATIONS["sued"]["lat"]]
    lons = [FOEHN_STATIONS["nord"]["lon"], FOEHN_STATIONS["sued"]["lon"]]

    params = {
        "latitude": ",".join(str(x) for x in lats),
        "longitude": ",".join(str(x) for x in lons),
        "hourly": (
            "pressure_msl,relative_humidity_2m,wind_speed_10m,wind_gusts_10m,"
            "wind_speed_700hPa,wind_direction_700hPa,surface_pressure,temperature_2m"
        ),
        "forecast_days": forecast_days,
        "timezone": config.TIMEZONE,
    }

    try:
        resp = requests.get(config.API_URL, params=params, timeout=config.API_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()

        # Multi-Point liefert Liste
        if isinstance(data, dict):
            data = [data]

        if len(data) < 2:
            return None

        return {"nord": data[0], "sued": data[1]}
    except Exception as e:
        return None


def evaluate_foehn(
    nord: dict,
    sued: dict,
    time_index: Optional[int] = None,
) -> dict:
    """
    Bewertet Föhn-Gefahr für einen Zeitpunkt.

    Returns:
        {
            "level": "none" | "caution" | "danger",
            "label": str,
            "message": str,
            "delta_p_hpa": float,
            "crest_wind_kmh": float,
            "crest_dir_deg": float,
            "humidity_nord": float,
            "gust_ratio": float,
            "indicators": list,
            "timestamp": str,
        }
    """
    h_nord = nord.get("hourly", {})
    h_sued = sued.get("hourly", {})

    times = h_nord.get("time", [])
    if not times:
        return _empty_result("Keine Zeitreihe")

    if time_index is None:
        now = datetime.now()
        now_str = now.strftime("%Y-%m-%dT%H:00")
        try:
            time_index = times.index(now_str)
        except ValueError:
            time_index = 0

    if time_index >= len(times):
        time_index = 0

    def get(arr, i):
        if arr is None or not isinstance(arr, list) or i >= len(arr):
            return None
        return arr[i]

    p_nord = get(h_nord.get("pressure_msl"), time_index)
    p_sued = get(h_sued.get("pressure_msl"), time_index)
    rh_nord = get(h_nord.get("relative_humidity_2m"), time_index)
    wind_10 = get(h_nord.get("wind_speed_10m"), time_index)
    gusts_10 = get(h_nord.get("wind_gusts_10m"), time_index)
    wind_700 = get(h_nord.get("wind_speed_700hPa"), time_index)
    dir_700 = get(h_nord.get("wind_direction_700hPa"), time_index)

    delta_p = None
    if p_sued is not None and p_nord is not None:
        delta_p = round(p_sued - p_nord, 1)

    crest_wind = wind_700
    crest_dir = dir_700 if dir_700 is not None else 0

    gust_ratio = None
    if wind_10 is not None and wind_10 > 0 and gusts_10 is not None:
        gust_ratio = round(gusts_10 / wind_10, 1)

    indicators = []
    level = "none"

    # 1. Druckgradient (Südföhn: Süd > Nord)
    if delta_p is not None:
        indicators.append(f"Delta-P (Sued-Nord): {delta_p} hPa")
        if delta_p >= THRESHOLD_DELTA_P_DANGER:
            level = "danger"
            indicators.append(f"Delta-P >= {THRESHOLD_DELTA_P_DANGER} hPa -> Flugverbot-Empfehlung")
        elif delta_p >= THRESHOLD_DELTA_P_CAUTION:
            if level != "danger":
                level = "caution"
            indicators.append(f"Delta-P >= {THRESHOLD_DELTA_P_CAUTION} hPa -> Vorsicht an exponierten Stellen")

    # 2. Höhenwind am Kamm (S/SW für Südföhn)
    if crest_wind is not None:
        indicators.append(f"Höhenwind 700 hPa: {round(crest_wind)} km/h aus {round(crest_dir or 0)}°")
        if crest_dir is not None and SUEDFOEHN_DIR_START <= crest_dir <= SUEDFOEHN_DIR_END:
            if crest_wind >= THRESHOLD_CREST_WIND_DANGER:
                level = "danger"
                indicators.append(f"Wind am Kamm >= {THRESHOLD_CREST_WIND_DANGER} km/h aus S/SW")
            elif crest_wind >= THRESHOLD_CREST_WIND_CAUTION:
                if level != "danger":
                    level = "caution"
                indicators.append("Starker Wind am Kamm aus S/SW")

    # 3. Luftfeuchtigkeit (trocken = Föhn durchgebrochen)
    if rh_nord is not None:
        indicators.append(f"Luftfeuchtigkeit: {round(rh_nord)}%")
        if rh_nord < THRESHOLD_HUMIDITY_LOW and level != "none":
            indicators.append("Trockene Föhnluft im Tal")

    # 4. Böigkeit
    if gust_ratio is not None and gust_ratio > THRESHOLD_GUST_RATIO:
        indicators.append(f"Böigkeit: {gust_ratio:.1f}× (turbulent)")
        if level == "caution":
            indicators.append("Starke Böen → zusätzliche Vorsicht")

    if level == "none" and delta_p is not None and delta_p > 0:
        indicators.append("Kein Föhn-Alarm, aber Druckgradient vorhanden.")

    label = {"none": "Kein Föhn", "caution": "Föhn-Vorsicht", "danger": "Föhn-Gefahr"}[level]
    message = _build_message(level, delta_p, crest_wind, crest_dir, rh_nord)

    return {
        "level": level,
        "label": label,
        "message": message,
        "delta_p_hpa": delta_p,
        "crest_wind_kmh": round(crest_wind, 0) if crest_wind is not None else None,
        "crest_dir_deg": round(crest_dir, 0) if crest_dir is not None else None,
        "humidity_nord": round(rh_nord, 0) if rh_nord is not None else None,
        "gust_ratio": gust_ratio,
        "indicators": indicators,
        "timestamp": times[time_index] if time_index < len(times) else "",
        "stations": FOEHN_STATIONS,
    }


def _build_message(
    level: str,
    delta_p: Optional[float],
    crest_wind: Optional[float],
    crest_dir: Optional[float],
    humidity: Optional[float],
) -> str:
    if level == "none":
        return "Keine Föhn-Warnung. Föhn ist für Gleitschirmflieger extrem gefährlich – bei Unsicherheit nicht starten."
    if level == "caution":
        return "Föhn-Vorsicht: ΔP oder Höhenwind erhöht. An exponierten Stellen vorsichtig sein. Föhn kann unvorhersehbar durchgreifen."
    return "Föhn-Gefahr: Flugverbot-Empfehlung. Starker Druckgradient oder Wind am Kamm. Föhn ist turbulent und tückisch."


def _empty_result(reason: str) -> dict:
    return {
        "level": "none",
        "label": "Keine Daten",
        "message": reason,
        "delta_p_hpa": None,
        "crest_wind_kmh": None,
        "crest_dir_deg": None,
        "humidity_nord": None,
        "gust_ratio": None,
        "indicators": [],
        "timestamp": "",
        "stations": FOEHN_STATIONS,
    }


def get_foehn_for_dashboard(forecast_days: int = 2) -> dict:
    """
    Liefert Föhn-Evaluation für die nächsten Flugstunden (heute + morgen).

    Gibt pro Tag die erste Bewertung im Flugstunden-Fenster zurück,
    plus die „schlimmste“ Stufe des Tages.
    """
    raw = fetch_foehn_data(forecast_days)
    if not raw:
        return {"success": False, "error": "Föhn-Daten konnten nicht geladen werden", "foehn": None}

    nord = raw["nord"]
    sued = raw["sued"]
    times = nord.get("hourly", {}).get("time", [])

    if not times:
        return {"success": True, "foehn": _empty_result("Keine Zeitreihe"), "hourly": []}

    from datetime import datetime as dt

    results_by_hour = []
    worst_level = "none"
    level_order = {"none": 0, "caution": 1, "danger": 2}

    for i, t in enumerate(times):
        try:
            d = dt.fromisoformat(t.replace("Z", "+00:00"))
            if d.hour < config.FLIGHT_HOURS_START or d.hour >= config.FLIGHT_HOURS_END:
                continue
        except Exception:
            continue

        ev = evaluate_foehn(nord, sued, time_index=i)
        results_by_hour.append({
            "time": t,
            "hour": d.hour,
            "level": ev["level"],
            "label": ev["label"],
            "delta_p_hpa": ev["delta_p_hpa"],
            "crest_wind_kmh": ev["crest_wind_kmh"],
        })

        if level_order.get(ev["level"], 0) > level_order.get(worst_level, 0):
            worst_level = ev["level"]

    # Repräsentative Bewertung: erste Flugstunde heute oder schlimmste
    first_today = next((r for r in results_by_hour if r["time"].startswith(
        dt.now().strftime("%Y-%m-%d"))), None)
    first_result = first_today or (results_by_hour[0] if results_by_hour else None)

    if first_result:
        ev = evaluate_foehn(nord, sued, time_index=times.index(first_result["time"]))
    else:
        ev = evaluate_foehn(nord, sued, time_index=0)

    ev["worst_level_today"] = worst_level
    ev["hourly"] = results_by_hour[:24]  # max 24 Einträge

    return {"success": True, "foehn": ev, "hourly": results_by_hour}


if __name__ == "__main__":
    r = get_foehn_for_dashboard()
    if r["success"]:
        f = r["foehn"]
        print(f"Foehn: {f['label']} ({f['level']})")
        print(f"  Delta-P: {f['delta_p_hpa']} hPa")
        print(f"  Hoehenwind 700hPa: {f['crest_wind_kmh']} km/h aus {f['crest_dir_deg']} deg")
        print(f"  Luftfeuchtigkeit: {f['humidity_nord']}%")
        for ind in f.get("indicators", []):
            print(f"  - {ind}")
    else:
        print("Fehler:", r.get("error"))
