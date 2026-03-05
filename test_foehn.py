import config
from foehn_indicators import evaluate_foehn

# Dummy data for extreme North Foehn
nord = {'hourly': {'time': ['2026-03-04T12:00'], 'pressure_msl': [1020], 'relative_humidity_2m': [80], 'wind_speed_10m': [10], 'wind_gusts_10m': [15], 'wind_speed_700hPa': [80], 'wind_direction_700hPa': [10]}}
sued = {'hourly': {'time': ['2026-03-04T12:00'], 'pressure_msl': [1010]}}

# Mute config log calls
import logging
logging.disable(logging.CRITICAL)

# Test 1: Uetliberg (Süd kritisch)
config.LOCATION['kritischer_foehn'] = 'Süd'
res1 = evaluate_foehn(nord, sued, 0)
print('Test 1 (Süd kritisch) Level:', res1['level'])
print('Indicators:', res1['indicators'])
print('-'*40)

# Test 2: Andere Location (Nord kritisch)
config.LOCATION['kritischer_foehn'] = 'Nord'
res2 = evaluate_foehn(nord, sued, 0)
print('Test 2 (Nord kritisch) Level:', res2['level'])
print('Indicators:', res2['indicators'])
