import json
import traceback
import sys
from datetime import datetime
from thermik_calculator import calculate_thermal_profile, calculate_dewpoint
from config import FLIGHT_HOURS_START, FLIGHT_HOURS_END, LOCATION

with open('data/wetterdaten.json', 'r', encoding='utf-8') as f:
    d = json.load(f)

hourly_data = d[list(d.keys())[0]].get('hourly_data', {})
pressure_level_data = d[list(d.keys())[0]].get('pressure_level_data', {})
hours = 3

sorted_times = sorted(hourly_data.keys())
lines = []
count = 0

for timestamp in sorted_times:
    try:
        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        if not (FLIGHT_HOURS_START <= dt.hour < FLIGHT_HOURS_END):
            continue
    except Exception:
        continue
        
    if count >= hours:
        break
    count += 1
    
    data = hourly_data[timestamp]
    time_str = timestamp.replace('T', ' ')[:16]
    
    # Exakte Logic aus _format_hourly_data
    try:
        p_levels = []
        for level in [1000, 975, 950, 925, 900, 875, 850, 825, 800, 775, 750, 700, 600]:
            h_val = pressure_level_data.get(timestamp, {}).get(f'geopotential_height_{level}hPa')
            t_val = pressure_level_data.get(timestamp, {}).get(f'temperature_{level}hPa')
            if h_val is not None and t_val is not None:
                p_levels.append({'pressure': level, 'height': h_val, 'temp': t_val})
        
        surf_dew = calculate_dewpoint(data.get('temperature_2m'), data.get('relative_humidity_2m', 50))
        
        therm = calculate_thermal_profile(
            surface_temp=data.get('temperature_2m'),
            surface_dewpoint=surf_dew,
            elevation_m=850.0,
            pressure_levels_data=p_levels,
            boundary_layer_height_agl=data.get('boundary_layer_height'),
            sunshine_duration_s=data.get('sunshine_duration'),
            shortwave_radiation=data.get('shortwave_radiation'),
            direct_radiation=data.get('direct_radiation'),
            diffuse_radiation=data.get('diffuse_radiation'),
            soil_moisture=data.get('soil_moisture_0_to_1cm'),
            soil_temperature=data.get('soil_temperature_0cm'),
            updraft=data.get('updraft'),
            et0=data.get('et0_fao_evapotranspiration'),
            vpd=data.get('vapour_pressure_deficit'),
            lifted_index=data.get('lifted_index'),
            convective_inhibition=data.get('convective_inhibition'),
            snow_depth=data.get('snow_depth'),
            timestamp=timestamp,
            slope_azimuth=LOCATION.get('slope_azimuth'),     # <-- Wichtiger Punkt
            slope_angle=LOCATION.get('slope_angle'),         # <-- Wichtiger Punkt
        )
        
        if 'error' not in therm:
            climb = therm['climb_rate']
            max_h = therm['max_height']
            lcl = therm.get('lcl')
            lcl_str = f", LCL/Basis {lcl}m" if lcl else ""
            thermal_info = f" | THERMIK-PROXY: {climb} m/s bis {max_h}m MSL{lcl_str} (Güte: {therm['rating']}/10)"
        else:
            thermal_info = f" | Thermik-Error-Key: {therm['error']}"
    except Exception as e:
        err_str = traceback.format_exc().split('\n')[-2]
        thermal_info = f" | Thermik-Fehler: {e} ({err_str})"
    
    print(f"{time_str}{thermal_info}")
