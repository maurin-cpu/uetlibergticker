import json
import os
from pathlib import Path
from datetime import datetime
import requests
import config
from thermik_calculator import calculate_dewpoint, calculate_thermal_profile


def fetch_and_calculate_regions():
    """
    Holt die Wetterdaten für alle 24 Regionen und berechnet das Thermik-Güte-Rating.

    Ablauf:
    1. API-Anfrage an Open-Meteo für alle Regionen gleichzeitig (Batch)
    2. Pro Region: Stündliche Thermik-Berechnung mit regionsspezifischer elevation_ref
    3. Aggregation zu Tageswerten (max climb, top3 rating, etc.)
    4. Speicherung als JSON (regions_forecast.json)

    Nutzt icon_seamless als Modell, das surface_sensible_heat_flux und
    surface_latent_heat_flux liefern kann. Zusätzlich shortwave_radiation
    als Fallback für die Wärmefluss-Schätzung.
    """
    days = config.FORECAST_DAYS
    results = {}

    print(f"INFO: Hole Regionen-Daten für {days} Tage ({len(config.REGIONS)} Regionen)...")

    lats = [str(r['lat']) for r in config.REGIONS]
    lons = [str(r['lon']) for r in config.REGIONS]

    pl_params = ",".join(config.PRESSURE_LEVEL_PARAMS)

    # icon_seamless unterstuetzt surface_sensible_heat_flux / surface_latent_heat_flux nicht
    unsupported_for_icon = {"surface_sensible_heat_flux", "surface_latent_heat_flux"}
    supported_hourly = [p for p in config.HOURLY_PARAMS if p not in unsupported_for_icon]
    # relative_humidity_2m + dewpoint_2m werden fuer Thermik-Berechnung benoetigt
    extra_params = ["relative_humidity_2m", "dewpoint_2m"]
    for ep in extra_params:
        if ep not in supported_hourly:
            supported_hourly.append(ep)

    hourly_params = ",".join(supported_hourly)

    params = {
        "latitude": ",".join(lats),
        "longitude": ",".join(lons),
        "models": "icon_seamless",
        "hourly": hourly_params + "," + pl_params,
        "forecast_days": days,
        "timezone": config.TIMEZONE
    }

    try:
        resp = requests.get(config.API_URL, params=params, timeout=30)
        resp.raise_for_status()
        data_array = resp.json()

        # Falls nur eine Region abgefragt wurde, kommt ein Dict zurück, sonst eine Liste
        if isinstance(data_array, dict):
            data_array = [data_array]

        for region_idx, region in enumerate(config.REGIONS):
            rid = region['id']
            name = region['name']
            lat = region['lat']
            lon = region['lon']
            # Regionsspezifische Referenzhöhe für den Paketaufstieg
            elevation_ref = region.get('elevation_ref', 800)

            data = data_array[region_idx]
            hourly = data.get("hourly", {})
            times = hourly.get("time", [])

            days_data = {}
            region_warnings = []

            for i, time_str in enumerate(times):
                dt = datetime.fromisoformat(time_str)
                date_str = dt.strftime("%Y-%m-%d")

                hour = dt.hour
                if hour < config.FLIGHT_HOURS_START or hour >= config.FLIGHT_HOURS_END:
                    continue

                if date_str not in days_data:
                    days_data[date_str] = []

                # --- Basis-Wetterdaten extrahieren ---
                surf_temp = _safe_get(hourly, "temperature_2m", i)
                rh = _safe_get(hourly, "relative_humidity_2m", i)
                blh = _safe_get(hourly, "boundary_layer_height", i)
                sun = _safe_get(hourly, "sunshine_duration", i)
                cape = _safe_get(hourly, "cape", i)

                if surf_temp is None:
                    continue

                # Taupunkt berechnen (falls nicht direkt verfügbar)
                surf_dew = _safe_get(hourly, "dewpoint_2m", i)
                if surf_dew is None and rh is not None:
                    surf_dew = calculate_dewpoint(surf_temp, rh)

                # --- Neue Flux-Parameter extrahieren ---
                shf = _safe_get(hourly, "surface_sensible_heat_flux", i)
                lhf = _safe_get(hourly, "surface_latent_heat_flux", i)
                swr = _safe_get(hourly, "shortwave_radiation", i)
                dir_rad = _safe_get(hourly, "direct_radiation", i)
                diff_rad = _safe_get(hourly, "diffuse_radiation", i)
                sm = _safe_get(hourly, "soil_moisture_0_to_1cm", i)
                st = _safe_get(hourly, "soil_temperature_0cm", i)
                upd = _safe_get(hourly, "updraft", i)
                et0_val = _safe_get(hourly, "et0_fao_evapotranspiration", i)
                vpd_val = _safe_get(hourly, "vapour_pressure_deficit", i)
                li_val = _safe_get(hourly, "lifted_index", i)
                cin_val = _safe_get(hourly, "convective_inhibition", i)

                # --- Höhenprofil extrahieren ---
                p_levels = []
                for level in config.PRESSURE_LEVELS:
                    h_key = f"geopotential_height_{level}hPa"
                    t_key = f"temperature_{level}hPa"
                    if h_key in hourly and t_key in hourly:
                        h_val = _safe_get(hourly, h_key, i)
                        t_val = _safe_get(hourly, t_key, i)
                        if h_val is not None and t_val is not None:
                            p_levels.append({
                                'pressure': level,
                                'height': h_val,
                                'temp': t_val
                            })

                # --- Thermik-Berechnung mit neuer Physik ---
                therm = calculate_thermal_profile(
                    surface_temp=surf_temp,
                    surface_dewpoint=surf_dew,
                    elevation_m=elevation_ref,
                    pressure_levels_data=p_levels,
                    boundary_layer_height_agl=blh,
                    sunshine_duration_s=sun,
                    surface_sensible_heat_flux=shf,
                    surface_latent_heat_flux=lhf,
                    shortwave_radiation=swr,
                    direct_radiation=dir_rad,
                    diffuse_radiation=diff_rad,
                    soil_moisture=sm,
                    soil_temperature=st,
                    updraft=upd,
                    et0=et0_val,
                    vpd=vpd_val,
                    lifted_index=li_val,
                    convective_inhibition=cin_val,
                )

                if "error" in therm:
                    therm = {
                        "climb_rate": 0, "rating": 0,
                        "max_height": 0, "lcl": 0,
                        "diagnostics": {}, "data_warnings": []
                    }

                # Warnungen sammeln (pro Region aggregiert)
                for w in therm.get("data_warnings", []):
                    if w not in region_warnings:
                        region_warnings.append(w)

                # Diagnostics extrahieren
                diag = therm.get("diagnostics", {})

                days_data[date_str].append({
                    "hour": hour,
                    "climb": therm.get("climb_rate", 0),
                    "rating": therm.get("rating", 0),
                    "max_height": therm.get("max_height", 0),
                    "lcl": therm.get("lcl", 0),
                    "cape": cape or 0,
                    "w_star_parcel": diag.get("w_star_parcel", 0),
                    "w_star_deardorff": diag.get("w_star_deardorff", 0),
                    "limiting_factor": diag.get("limiting_factor", ""),
                    "sensible_heat_flux": diag.get("sensible_heat_flux", 0),
                    "bowen_ratio": diag.get("bowen_ratio"),
                })

            # --- Tageswerte aggregieren ---
            region_daily = {}
            for d, hourly_records in days_data.items():
                if not hourly_records:
                    continue
                max_climb = max(r["climb"] for r in hourly_records)
                max_height = max(r["max_height"] for r in hourly_records)
                ratings = sorted([r["rating"] for r in hourly_records], reverse=True)
                top3_rating = sum(ratings[:3]) / min(len(ratings), 3) if ratings else 0
                max_cape = max(r["cape"] for r in hourly_records)
                lcls = [r["lcl"] for r in hourly_records if r["lcl"] and r["lcl"] > 0]
                avg_lcl = sum(lcls) / len(lcls) if lcls else 0

                region_daily[d] = {
                    "climb_rate": round(max_climb, 1),
                    "rating": round(top3_rating),
                    "max_height": round(max_height),
                    "lcl": round(avg_lcl),
                    "cape": round(max_cape),
                    "hourly": hourly_records,
                }

            results[rid] = {
                "id": rid,
                "name": name,
                "lat": lat,
                "lon": lon,
                "elevation_ref": elevation_ref,
                "daily": region_daily,
                "data_warnings": region_warnings,
            }
            print(f"  -> {name} (elev={elevation_ref}m) berechnet.")

        # --- Rohe Wetterdaten pro Region extrahieren und in InstantDB speichern ---
        region_raw = {}
        try:
            for region_idx, region in enumerate(config.REGIONS):
                rid = region['id']
                hourly = data_array[region_idx].get("hourly", {})
                times = hourly.get("time", [])

                hourly_data = {}
                pressure_level_data = {}
                all_hourly_params = list(config.HOURLY_PARAMS) + ["relative_humidity_2m", "dewpoint_2m"]
                for i, time_str in enumerate(times):
                    h_entry = {}
                    for param in all_hourly_params:
                        val = _safe_get(hourly, param, i)
                        if param == "cloud_base" and val is not None and val > 6000:
                            val = None
                        h_entry[param] = val
                    hourly_data[time_str] = h_entry

                    pl_entry = {}
                    for level in config.PRESSURE_LEVELS:
                        for var in ["temperature", "relative_humidity", "wind_speed", "wind_direction", "geopotential_height"]:
                            key = f"{var}_{level}hPa"
                            pl_entry[key] = _safe_get(hourly, key, i)
                    pressure_level_data[time_str] = pl_entry

                region_raw[rid] = {"hourly_data": hourly_data, "pressure_level_data": pressure_level_data}

            from instantdb_helper import save_all_regions_weather
            ok = save_all_regions_weather(region_raw)
            print(f"[{'OK' if ok else 'FEHLER'}] Regionen-Wetterdaten in InstantDB gespeichert ({len(region_raw)} Regionen)")
        except Exception as e:
            print(f"[WARNUNG] Regionen-Rohdaten konnten nicht in InstantDB gespeichert werden: {e}")
            import traceback
            traceback.print_exc()

    except Exception as e:
        print(f"Allgemeiner Fehler bei API-Abfrage: {e}")
        import traceback
        traceback.print_exc()

    output_path = config.get_data_dir() / "regions_forecast.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"[OK] {len(results)} Regionen erfolgreich in {output_path} gespeichert.")


def _safe_get(hourly: dict, key: str, index: int):
    """Sicherer Zugriff auf stündliche API-Daten. Gibt None zurück bei fehlenden Daten."""
    arr = hourly.get(key)
    if arr is None or not isinstance(arr, list) or len(arr) <= index:
        return None
    return arr[index]


if __name__ == "__main__":
    fetch_and_calculate_regions()
