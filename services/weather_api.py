import os
import requests
from datetime import datetime, timedelta
import json

class WeatherService:
    def __init__(self, api_key=None):
        """Initialize the weather service with API key"""
        self.api_key = api_key or os.environ.get("WEATHER_API_KEY")
        self.base_url = "https://api.openweathermap.org/data/2.5"
        self.cache_file = "data/weather_cache.json"
        self.cache = self._load_cache()
    
    def _load_cache(self):
        """Load weather cache from file"""
        try:
            with open(self.cache_file, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
    
    def _save_cache(self):
        """Save weather cache to file"""
        os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
        with open(self.cache_file, 'w') as f:
            json.dump(self.cache, f)
    
    def _cache_key(self, city, date):
        """Generate a cache key for a city and date"""
        return f"{city.lower()}_{date}"
    
    def get_weather(self, city, date=None):
        """Get weather forecast for a city on a specific date"""
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")
        
        # Check cache first
        cache_key = self._cache_key(city, date)
        if cache_key in self.cache:
            cached_data = self.cache[cache_key]
            # Check if cache is still valid (less than 6 hours old)
            if datetime.now().timestamp() - cached_data["timestamp"] < 6 * 3600:
                return cached_data["data"]
        
        # If no API key, return mock data
        if not self.api_key:
            return self._get_mock_weather(city, date)
        
        # Calculate days from today
        today = datetime.now().date()
        target_date = datetime.strptime(date, "%Y-%m-%d").date()
        days_diff = (target_date - today).days
        
        if days_diff < 0:
            # For past dates, return mock historical data
            return self._get_mock_weather(city, date, historical=True)
        elif days_diff <= 7:
            # For next 7 days, use forecast API
            url = f"{self.base_url}/forecast"
            params = {
                "q": city,
                "appid": self.api_key,
                "units": "metric",
                "cnt": 7  # 7 day forecast
            }
            
            try:
                response = requests.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                
                # Extract forecast for the specific date
                for forecast in data["list"]:
                    forecast_date = datetime.fromtimestamp(forecast["dt"]).strftime("%Y-%m-%d")
                    if forecast_date == date:
                        weather_data = self._format_weather_data(forecast, city)
                        
                        # Cache the result
                        self.cache[cache_key] = {
                            "data": weather_data,
                            "timestamp": datetime.now().timestamp()
                        }
                        self._save_cache()
                        
                        return weather_data
                
                # If specific date not found in forecast, return best estimate
                weather_data = self._format_weather_data(data["list"][0], city)
                
                # Cache the result
                self.cache[cache_key] = {
                    "data": weather_data,
                    "timestamp": datetime.now().timestamp()
                }
                self._save_cache()
                
                return weather_data
                
            except Exception as e:
                print(f"Error fetching weather data: {e}")
                return self._get_mock_weather(city, date)
        else:
            # For dates beyond 7 days, use historical averages or climate data
            return self._get_mock_weather(city, date)
    
    def _format_weather_data(self, raw_data, city):
        """Format raw weather API response into a clean format"""
        return {
            "city": city,
            "date": datetime.fromtimestamp(raw_data["dt"]).strftime("%Y-%m-%d"),
            "description": raw_data["weather"][0]["description"],
            "icon": raw_data["weather"][0]["icon"],
            "temp": {
                "day": raw_data["main"]["temp"],
                "min": raw_data["main"]["temp_min"],
                "max": raw_data["main"]["temp_max"]
            },
            "humidity": raw_data["main"]["humidity"],
            "wind_speed": raw_data["wind"]["speed"],
            "precipitation": raw_data.get("rain", {}).get("3h", 0),
            "source": "openweathermap"
        }
    
    def _get_mock_weather(self, city, date, historical=False):
        """Generate mock weather data for testing or when API is unavailable"""
        # Generate a pseudo-random but consistent weather based on city and date
        city_hash = sum(ord(c) for c in city.lower())
        date_hash = sum(ord(c) for c in date)
        combined_hash = (city_hash + date_hash) % 100
        
        # Map the hash to weather conditions
        if combined_hash < 20:
            condition = "rainy"
            icon = "10d"
        elif combined_hash < 40:
            condition = "cloudy"
            icon = "03d"
        elif combined_hash < 60:
            condition = "partly cloudy"
            icon = "02d"
        else:
            condition = "sunny"
            icon = "01d"
        
        # Generate pseudo-random temperature based on city and date
        base_temp = 15  # Base temperature in Celsius
        
        # Adjust for season (assuming Northern Hemisphere)
        month = int(date.split('-')[1])
        season_adj = abs(((month + 5) % 12) - 6) - 3  # -3 for winter, +3 for summer
        
        # City-specific temperature adjustments
        if "paris" in city.lower():
            city_temp = 15
        elif "london" in city.lower():
            city_temp = 12
        elif "rome" in city.lower() or "bangkok" in city.lower():
            city_temp = 25
        elif "new york" in city.lower():
            city_temp = 18
        elif "tokyo" in city.lower():
            city_temp = 20
        else:
            # Default temperature with slight randomization based on city name
            city_temp = base_temp + (city_hash % 10)
        
        # Calculate final temperature with some randomness
        final_temp = city_temp + season_adj + (combined_hash % 10) - 5
        
        return {
            "city": city,
            "date": date,
            "description": condition,
            "icon": icon,
            "temp": {
                "day": final_temp,
                "min": final_temp - 5,
                "max": final_temp + 5
            },
            "humidity": 50 + (combined_hash % 40),
            "wind_speed": 5 + (combined_hash % 20),
            "precipitation": 0 if condition != "rainy" else 5 + (combined_hash % 10),
            "source": "mock" if not historical else "historical_mock"
        }
    
    def get_forecast(self, city, start_date, end_date):
        """Get weather forecast for a range of dates"""
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        
        forecast = []
        current_date = start
        
        while current_date <= end:
            date_str = current_date.strftime("%Y-%m-%d")
            weather = self.get_weather(city, date_str)
            forecast.append(weather)
            current_date += timedelta(days=1)
        
        return forecast