import requests
from pprint import pprint

url = "https://api.open-meteo.com/v1/forecast"
params = {
    "latitude": 47.3226,
    "longitude": 8.5008,
    "models": "meteoswiss_icon_ch1",
    "hourly": "cloud_base",
    "forecast_days": 3,
    "timezone": "Europe/Berlin"
}

resp = requests.get(url, params=params)
data = resp.json()

print("ICON-CH1 cloud_base:")
for t, cb in zip(data['hourly']['time'], data['hourly']['cloud_base']):
    if "13:00" in t or "14:00" in t or "15:00" in t or "16:00" in t:
        print(f"{t}: {cb}")

params["models"] = "icon_seamless"
resp = requests.get(url, params=params)
data = resp.json()

print("\nSeamless cloud_base:")
for t, cb in zip(data['hourly']['time'], data['hourly']['cloud_base']):
    if "13:00" in t or "14:00" in t or "15:00" in t or "16:00" in t:
        print(f"{t}: {cb}")
