import json
import traceback
import sys
from datetime import datetime
from thermik_calculator import calculate_thermal_profile, calculate_dewpoint
from config import FLIGHT_HOURS_START, FLIGHT_HOURS_END, LOCATION

print('Starting diag2.py')
sys.stdout.flush()

try:
    with open('data/wetterdaten.json', 'r', encoding='utf-8') as f:
        d = json.load(f)
    k = list(d.keys())[0]
    hd = d[k].get('hourly_data', {})
    pd_levels = d[k].get('pressure_level_data', {})

    for ts in sorted(hd.keys()):
        dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
        if FLIGHT_HOURS_START <= dt.hour < FLIGHT_HOURS_END:
            data = hd[ts]
            print(f'Testing {ts} (Hour {dt.hour})')
            sys.stdout.flush()
            try:
                p_levels = []
                for level in [1000, 975, 950, 925, 900, 875, 850, 825, 800, 775, 750, 700, 600]:
                    h_val = pd_levels.get(ts, {}).get(f'geopotential_height_{level}hPa')
                    t_val = pd_levels.get(ts, {}).get(f'temperature_{level}hPa')
                    if h_val is not None and t_val is not None:
                        p_levels.append({'pressure': level, 'height': h_val, 'temp': t_val})
                print('Data prepared')
                sys.stdout.flush()
                surf_dew = calculate_dewpoint(data.get('temperature_2m'), data.get('relative_humidity_2m', 50))
                print('Starting calc')
                sys.stdout.flush()
                therm = calculate_thermal_profile(
                    surface_temp=data.get('temperature_2m'), surface_dewpoint=surf_dew, elevation_m=850.0,
                    pressure_levels_data=p_levels, boundary_layer_height_agl=data.get('boundary_layer_height'),
                    sunshine_duration_s=data.get('sunshine_duration'), shortwave_radiation=data.get('shortwave_radiation'),
                    direct_radiation=data.get('direct_radiation'), diffuse_radiation=data.get('diffuse_radiation'),
                    soil_moisture=data.get('soil_moisture_0_to_1cm'), soil_temperature=data.get('soil_temperature_0cm'),
                    updraft=data.get('updraft'), et0=data.get('et0_fao_evapotranspiration'),
                    vpd=data.get('vapour_pressure_deficit'), lifted_index=data.get('lifted_index'),
                    convective_inhibition=data.get('convective_inhibition'), snow_depth=data.get('snow_depth'),
                    timestamp=ts, slope_azimuth=LOCATION.get('slope_azimuth'), slope_angle=LOCATION.get('slope_angle')
                )
                print('Calc done! keys=', list(therm.keys()))
                sys.stdout.flush()
            except Exception as e:
                print('LOOP ERROR:')
                traceback.print_exc()
                sys.stdout.flush()
            break
    print('END OF SCRIPT')
except Exception as e:
    print('OUTER ERROR')
    traceback.print_exc()
