import json
import logging
from datetime import datetime
from config import LOCATION, PRESSURE_LEVELS
from thermik_calculator import calculate_thermal_profile, calculate_dewpoint
from instantdb_helper import load_weather_data

logging.basicConfig(level=logging.INFO)

def run_diagnostics():
    data = load_weather_data()
    if not data:
        print("No instantdb data")
        return

    # Find uetliberg location
    loc_key = None
    for k in data.keys():
        if 'uetliberg' in k.lower():
            loc_key = k
            break

    if not loc_key:
        print("Uetliberg not found")
        return
        
    weather = data[loc_key]
    hourly = weather.get("hourly_data", {})
    pressure = weather.get("pressure_level_data", {})

    print(f"Loaded {len(hourly)} hourly records for {loc_key}")

    for ts in sorted(hourly.keys()):
        if not ts.startswith("2026-03-05"):
            continue

        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if dt.hour < 9 or dt.hour > 17:
            continue

        h_data = hourly[ts]
        p_data = pressure.get(ts, {})
        
        surf_temp = h_data.get('temperature_2m')
        surf_dew = calculate_dewpoint(surf_temp, h_data.get('relative_humidity_2m', 50))

        p_levels = []
        for level in PRESSURE_LEVELS:
            h_val = p_data.get(f'geopotential_height_{level}hPa')
            t_val = p_data.get(f'temperature_{level}hPa')
            if h_val is not None and t_val is not None:
                p_levels.append({'pressure': level, 'height': h_val, 'temp': t_val})

        if surf_temp is None or not p_levels:
            continue

        elev_ref = LOCATION.get('elevation_ref', 850.0)

        therm = calculate_thermal_profile(
            surface_temp=surf_temp,
            surface_dewpoint=surf_dew,
            elevation_m=elev_ref,
            pressure_levels_data=p_levels,
            boundary_layer_height_agl=h_data.get('boundary_layer_height'),
            sunshine_duration_s=h_data.get('sunshine_duration'),
            surface_sensible_heat_flux=h_data.get('surface_sensible_heat_flux'),
            surface_latent_heat_flux=h_data.get('surface_latent_heat_flux'),
            shortwave_radiation=h_data.get('shortwave_radiation'),
            direct_radiation=h_data.get('direct_radiation'),
            diffuse_radiation=h_data.get('diffuse_radiation'),
            soil_moisture=h_data.get('soil_moisture_0_to_1cm'),
            soil_temperature=h_data.get('soil_temperature_0cm'),
            updraft=h_data.get('updraft'),
            et0=h_data.get('et0_fao_evapotranspiration'),
            vpd=h_data.get('vapour_pressure_deficit'),
            lifted_index=h_data.get('lifted_index'),
            convective_inhibition=h_data.get('convective_inhibition'),
            snow_depth=h_data.get('snow_depth'),
            timestamp=ts,
            slope_azimuth=LOCATION.get('slope_azimuth'),
            slope_angle=LOCATION.get('slope_angle'),
        )

        climb = therm.get('climb_rate', 0)
        max_h = therm.get('max_height', 0)
        diag = therm.get('diagnostics', {})
        warn = therm.get('data_warnings', [])
        try:
            with open("diag_bug.txt", "a", encoding="utf-8") as f:
                f.write(f"\n--- {ts} ---\n")
                f.write(f"Climb Rate: {climb} m/s | Max Height: {max_h}m\n")
                f.write(f"H flux: {diag.get('sensible_heat_flux')} W/m2 (estimated: {diag.get('sensible_heat_flux_estimated')})\n")
                f.write(f"w* Parcel: {diag.get('w_star_parcel')} | w* Deardorff: {diag.get('w_star_deardorff')}\n")
                f.write(f"Limiting factor: {diag.get('limiting_factor')} | BLH: {diag.get('boundary_layer_height_agl')}\n")
                f.write(f"Warnings: {json.dumps(warn, ensure_ascii=True)}\n")
        except Exception as e:
            pass

if __name__ == '__main__':
    open("diag_bug.txt", "w", encoding="utf-8").close()
    run_diagnostics()
