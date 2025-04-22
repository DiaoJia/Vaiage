import os
import googlemaps
import sys
import pathlib

# Add the project root to the Python path
sys.path.append(str(pathlib.Path(__file__).parent.parent))

from services.maps_api import POIApi
from services.weather_api import WeatherService
from services.car_rental_api import CarRentalService
import unittest
from datetime import datetime
import json


class InformationAgent:
    """
    Information Agent
    
    This agent integrates multiple information services including:
    - Points of Interest (POI) search
    - Route planning
    - Weather forecasting
    - Car rental search
    
    All external information is retrieved through this agent, providing a single interface
    for travel-related data needs.
    
    Usage:
        agent = UnifiedInformationAgent()
        
        # Find points of interest
        pois = agent.find_pois(lat=37.8715, lng=-122.2730, number=5, poi_type="tourist_attraction")
        
        # Plan routes between locations
        routes = agent.plan_routes(origin="University of California, Berkeley, CA", 
                                  destination="Chase Center, San Francisco, CA")
        
        # Get weather forecast
        weather = agent.get_weather(lat=37.8715, lng=-122.2730, start_date="2023-04-18", duration=3)
        
        # Search for car rentals
        cars = agent.search_car_rentals(location="San Francisco", 
                                       start_date="2023-05-01", 
                                       end_date="2023-05-05")
    """
    def __init__(self, maps_api_key=None, car_api_key=None):
        # Initialize Google Maps API
        self.maps_api_key = maps_api_key or os.getenv("MAPS_API_KEY")
        self.gmaps = googlemaps.Client(key=self.maps_api_key)
        # POI service
        self.poi_api = POIApi(self.maps_api_key)
        # Weather service
        self.weather_service = WeatherService()
        # Car rental service
        self.car_rental_service = CarRentalService(api_key=car_api_key)

    def city2geocode(self, city: str):
        """
        Convert city name to coordinates (latitude and longitude)
        """
        coordinates = self.gmaps.geocode(city)
        if not coordinates:
            return None
        return coordinates[0]['geometry']['location']
    
    def get_attractions(self, lat: float, lng: float, number: int = 10,
                  poi_type: str = None, sort_by: str = None, radius: int = 5000):
        """
        Find Points of Interest:
        
        Input:
            - lat: Latitude
            - lng: Longitude
            - number: Number of results to return (default: 10)
            - poi_type: Type of POI (e.g., "restaurant", "museum", "tourist_attraction")
            - sort_by: Sorting method ('price' or 'rating')
            - radius: Search radius in meters (default: 5000)
            
        Output:
            List of POIs containing information such as description, rating, price level,
            opening hours, address, etc.
            
        Example:
            [
                {
                    "id": "ChIJN1t_tDeuEmsRUsoyG83frY4",
                    "name": "Museum of Modern Art",
                    "rating": 4.5,
                    "price_level": 2,
                    "opening_hours": ["Monday: 10:00 AM – 5:30 PM", "Tuesday: 10:00 AM – 5:30 PM"],
                    "address": "151 3rd St, San Francisco, CA 94103",
                    "location": {"lat": 37.7857, "lng": -122.4011},
                    "category": "museum",
                    "estimated_duration": "2 hours"
                },
                ...
            ]
        """
        location = (lat, lng)
        # Use Google Maps Nearby Search
        results = self.gmaps.places_nearby(
            location=location,
            radius=radius,
            type=poi_type,
            language='en'
        ).get('results', [])

        # Take only the first 'number' results
        pois = []
        for place in results[:number]:
            pid = place.get('place_id')
            details = self.poi_api.get_poi_details(
                place_id=pid,
                fields=['name', 'rating', 'price_level', 'opening_hours', 'formatted_address', 'geometry']
            ).get('result', {})

            # Extract location information
            location = details.get('geometry', {}).get('location', {})
            
            # Extract category from the initial search results
            category = ""
            if place.get('types') and len(place.get('types')) > 0:
                category = place.get('types')[0]
            
            # Estimate duration based on category and other factors
            estimated_duration = self.estimate_duration(category, details)

            pois.append({
                'id': pid,
                'name': details.get('name'),
                'rating': details.get('rating'),
                'price_level': details.get('price_level'),
                'opening_hours': details.get('opening_hours', {}).get('weekday_text'),
                'address': details.get('formatted_address'),
                'location': {
                    'lat': location.get('lat'),
                    'lng': location.get('lng')
                },
                'category': category,
                'estimated_duration': estimated_duration
            })

        # Sort results
        if sort_by == 'price':
            pois.sort(key=lambda x: x.get('price_level') or 0)
        elif sort_by == 'rating':
            pois.sort(key=lambda x: x.get('rating') or 0, reverse=True)
        return pois

    def estimate_duration(self, category, details):
        """
        Estimate the duration for a given category and details.
        """
        category_duration = {
            'restaurant': 2,
            'museum': 2,
            'park': 2,
            'tourist_attraction': 2,
            'night_club': 3,
            'shopping_mall': 3,
            'zoo': 3,
            'amusement_park': 6
        }
        

        # Default duration if category is not found
        default_duration = 2
        
        # Get duration based on category
        duration = category_duration.get(category, default_duration)
        
        # Adjust duration based on rating
        rating = details.get('rating', 0)
        if rating > 4.5:
            duration *= 1.5
        elif rating < 3:
            duration *= 0.75
        
        return duration

    def plan_routes(self, origin: str, destination: str):
        """
        Route Planning:
        
        Input:
            - origin: Starting point (address or coordinates)
            - destination: End point (address or coordinates)
            
        Output:
            List of routes for different travel modes (driving, walking, bicycling, transit),
            including time, distance, and cost (if available)
            
        Example:
            [
                {
                    "mode": "driving",
                    "distance": "10.2 miles",
                    "duration": "25 mins"
                },
                {
                    "mode": "transit",
                    "distance": "10.5 miles",
                    "duration": "45 mins",
                    "fare": "$2.75"
                },
                ...
            ]
        """
        modes = ['driving', 'walking', 'bicycling', 'transit']
        routes = []
        for mode in modes:
            directions = self.gmaps.directions(
                origin, destination, mode=mode, language='en'
            )
            if not directions:
                continue
            leg = directions[0]['legs'][0]
            info = {
                'mode': mode,
                'distance': leg['distance']['text'],
                'duration': leg['duration']['text'],
            }
            # If fare information is available
            if 'fare' in directions[0]:
                info['fare'] = directions[0]['fare'].get('text')
            routes.append(info)
        return routes

    def get_weather(self, lat: float, lng: float, start_date: str, duration: int):
        """
        Weather Forecast:
        
        Input:
            - lat: Latitude
            - lng: Longitude
            - start_date: Start date (YYYY-MM-DD)
            - duration: Number of days
            
        Output:
            Detailed weather forecast
            
        Example:
            [
                {
                    "date": "2023-04-18",
                    "max_temp": "22 °C",
                    "min_temp": "15 °C",
                    "precipitation": "0 mm",
                    "wind_speed": "12 km/h",
                    "precipitation_probability": "5%",
                    "uv_index": "7"
                },
                ...
            ]
        """
        return self.weather_service.get_weather(lat, lng, start_date, duration)

    def search_car_rentals(self, location: str, start_date: str, end_date: str,
                           min_price: float = None, max_price: float = None, top_n: int = 5):
        """
        Car Rental Search:
        
        Input:
            - location: Location
            - start_date: Pickup date
            - end_date: Return date
            - min_price: Minimum price (optional)
            - max_price: Maximum price (optional)
            - top_n: Number of results to return (default: 5)
            
        Output:
            Top N car rental options, including car type, price, pickup/return locations, links, etc.
            
        Example:
            [
                {
                    "car_type": "Economy",
                    "model": "Toyota Corolla or similar",
                    "total_price": 175.50,
                    "daily_rate": 35.10,
                    "pickup_location": "SFO Airport",
                    "company": "Hertz",
                    "booking_link": "https://example.com/booking/123"
                },
                ...
            ]
        """
        result = self.car_rental_service.search_available_cars(
            location=location,
            start_date=start_date,
            end_date=end_date
        )
        cars = result.get('available_cars', [])
        # Price filtering
        if min_price is not None:
            cars = [c for c in cars if c.get('total_price', 0) >= min_price]
        if max_price is not None:
            cars = [c for c in cars if c.get('total_price', 0) <= max_price]
        # Sort by total price
        cars.sort(key=lambda x: x.get('total_price', 0))
        return cars[:top_n]
