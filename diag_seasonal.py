import sys
from datetime import datetime
from thermik_calculator import calculate_thermal_profile

# Mock profile
profile = [
    {'pressure': 1000, 'height': 150, 'temp': 12.0},
    {'pressure': 950, 'height': 500, 'temp': 9.0},
    {'pressure': 900, 'height': 900, 'temp': 5.0},
    {'pressure': 850, 'height': 1400, 'temp': 1.0},
    {'pressure': 800, 'height': 1900, 'temp': -3.0},
    {'pressure': 700, 'height': 3000, 'temp': -12.0},
]

scenarios = [
    {
        "name": "Frühling (Lush Vegetation) - Flachland",
        "timestamp": "2026-05-15T12:00:00Z",
        "slope_azimuth": 180,
        "slope_angle": 0,
        "snow_depth": 0.0,
        "dir_rad": 600, "diff_rad": 150
    },
    {
        "name": "Frühling (Lush Vegetation) - Südhang 30°",
        "timestamp": "2026-05-15T12:00:00Z",
        "slope_azimuth": 180,
        "slope_angle": 30,
        "snow_depth": 0.0,
        "dir_rad": 600, "diff_rad": 150
    },
    {
        "name": "Winter (Tiefstehend) - Flachland",
        "timestamp": "2026-01-15T12:00:00Z",
        "slope_azimuth": 180,
        "slope_angle": 0,
        "snow_depth": 0.0,
        "dir_rad": 300, "diff_rad": 100
    },
    {
        "name": "Winter (Tiefstehend) - Südhang 30°",
        "timestamp": "2026-01-15T12:00:00Z",
        "slope_azimuth": 180,
        "slope_angle": 30,
        "snow_depth": 0.0,
        "dir_rad": 300, "diff_rad": 100
    },
    {
        "name": "Winter - Tiefschnee (Flachland)",
        "timestamp": "2026-01-15T12:00:00Z",
        "slope_azimuth": 180,
        "slope_angle": 0,
        "snow_depth": 0.2, # 20cm
        "dir_rad": 300, "diff_rad": 100
    },
    {
        "name": "Spätsommer (Dry / Autumn Bonus) - Südhang 30°",
        "timestamp": "2026-09-01T14:00:00Z",
        "slope_azimuth": 225, # SW
        "slope_angle": 30,
        "snow_depth": 0.0,
        "dir_rad": 550, "diff_rad": 100
    }
]

print("=== Saisonale Thermik-Diagnostik ===\\n")

for sc in scenarios:
    print(f"\\n[{sc['name']}]")
    res = calculate_thermal_profile(
        surface_temp=10.0,
        surface_dewpoint=5.0,
        elevation_m=500,
        pressure_levels_data=profile,
        direct_radiation=sc['dir_rad'],
        diffuse_radiation=sc['diff_rad'],
        sunshine_duration_s=3600,
        timestamp=sc['timestamp'],
        slope_azimuth=sc['slope_azimuth'],
        slope_angle=sc['slope_angle'],
        snow_depth=sc['snow_depth']
    )
    
    if 'error' in res:
        print(f" Fehler: {res['error']}")
        continue
        
    print(f"  Climb Rate : {res['climb_rate']} m/s")
    print(f"  Max Height : {res['max_height']} m")
    print(f"  Rating     : {res['rating']}/10")
    for w in res.get('data_warnings', []):
        if "H geschätzt" in w or "Schneedecke" in w:
            print(f"  Info       : {w}")

print("\\nFertig.")
