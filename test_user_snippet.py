import openmeteo_requests
import requests_cache
import pandas as pd
from retry_requests import retry
import json

# Setup the Open-Meteo API client with cache and retry on error
cache_session = requests_cache.CachedSession('.cache', expire_after = 3600)
retry_session = retry(cache_session, retries = 5, backoff_factor = 0.2)
openmeteo = openmeteo_requests.Client(session = retry_session)

# Make sure all required weather variables are listed here
# The order of variables in hourly or daily is important to assign them correctly below
url = "https://api.open-meteo.com/v1/forecast"
params = {
	"latitude": 47.37,
	"longitude": 8.55,
	"hourly": ["precipitation", "cloud_cover", "cloud_base"],
	"models": "meteoswiss_icon_ch1",
	"timezone": "Europe/Berlin",
	"forecast_days": 3,
    "past_hours": 0
}
try:
    responses = openmeteo.weather_api(url, params=params)
    response = responses[0]
    
    hourly = response.Hourly()
    hourly_cloud_base = hourly.Variables(2).ValuesAsNumpy()
    
    dates = pd.date_range(
        start = pd.to_datetime(hourly.Time(), unit = "s", utc = True),
        end =  pd.to_datetime(hourly.TimeEnd(), unit = "s", utc = True),
        freq = pd.Timedelta(seconds = hourly.Interval()),
        inclusive = "left"
    )
    
    # Print Day 3 data
    print("Checking Day 3 Data for Cloud Base:")
    for date, val in zip(dates, hourly_cloud_base):
        # Check if date is 2 days from now (Day 3)
        # Using simple string check for Jan 13 (today is Jan 11)
        if "2026-01-13" in str(date):
             print(f"{date}: {val}")

except Exception as e:
    print(e)
