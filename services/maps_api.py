"""
This module provides a service for retrieving maps data using the Google Maps API.

You should input the address of the location, and the module will return the latitude and longitude of the location.


"""

import os
import requests
import json
import math
from datetime import datetime
import googlemaps
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class MapsService:
    def __init__(self, api_key=None):
        """Initialize the maps service with API key"""
        self.api_key = api_key or os.environ.get("MAPS_API_KEY")
        self.base_url = "https://maps.googleapis.com/maps/api"
        self.cache_file = "data/maps_cache.json"
        self.cache = self._load_cache()
    
    def _load_cache(self):
        """Load maps cache from file"""
        try:
            with open(self.cache_file, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
    
    def _save_cache(self):
        """Save maps cache to file"""
        os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
        with open(self.cache_file, 'w') as f:
            json.dump(self.cache, f)
    
    def _cache_key(self, endpoint, **params):
        """Generate a cache key for API requests"""
        param_str = "_".join(f"{k}_{v}" for k, v in sorted(params.items()))
        return f"{endpoint}_{param_str}"
    
    def geocode(self, address):
        """Convert address to coordinates"""
        # Check cache first
        cache_key = self._cache_key("geocode", address=address.lower())
        if cache_key in self.cache:
            cached_data = self.cache[cache_key]
            # Check if cache is still valid (less than 30 days old)
            if datetime.now().timestamp() - cached_data["timestamp"] < 30 * 24 * 3600:
                return cached_data["data"]
        
        # If no API key, return mock data
        if not self.api_key:
            result = self._get_mock_geocode(address)
            
            # Cache the result
            self.cache[cache_key] = {
                "data": result,
                "timestamp": datetime.now().timestamp()
            }
            self._save_cache()
            
            return result
        
        # Make API call to geocoding service
        try:
            url = f"{self.base_url}/geocode/json"
            params = {
                "address": address,
                "key": self.api_key
            }
            
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if data['status'] == 'OK':
                result = {
                    "address": address,
                    "lat": data['results'][0]['geometry']['location']['lat'],
                    "lng": data['results'][0]['geometry']['location']['lng'],
                    "formatted_address": data['results'][0]['formatted_address']
                }
            else:
                result = self._get_mock_geocode(address)
            
            # Cache the result
            self.cache[cache_key] = {
                "data": result,
                "timestamp": datetime.now().timestamp()
            }
            self._save_cache()
            
            return result
            
        except Exception as e:
            print(f"Error geocoding address: {e}")
            return self._get_mock_geocode(address)
    
    def _format_step(self, step):
        """Format a step from the Google Directions API"""
        return {
            "distance": step['distance']['text'],
            "duration": step['duration']['text'],
            "instructions": step['html_instructions'],
            "start_location": {
                "lat": step['start_location']['lat'],
                "lng": step['start_location']['lng']
            },
            "end_location": {
                "lat": step['end_location']['lat'],
                "lng": step['end_location']['lng']
            }
        }

    def _format_photos(self, photos):
        """Format photo references from Places API"""
        result = []
        for photo in photos:
            result.append({
                "reference": photo.get('photo_reference', ''),
                "width": photo.get('width', 400),
                "height": photo.get('height', 300)
            })
        return result

    def _format_opening_hours(self, opening_hours):
        """Format opening hours from Place Details API"""
        result = {}
        weekday_text = opening_hours.get('weekday_text', [])
        
        days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        for i, day in enumerate(days):
            if i < len(weekday_text):
                # Extract hours from format "Monday: 9:00 AM – 5:00 PM"
                hours = weekday_text[i].split(':', 1)[1].strip()
                result[day] = hours
            else:
                result[day] = "9:00 AM – 5:00 PM"
        
        return result
    
    def _format_reviews(self, reviews):
        """Format reviews from Place Details API"""
        result = []
        for review in reviews:
            result.append({
                "author": review.get('author_name', 'Anonymous'),
                "rating": review.get('rating', 0),
                "time": review.get('time', 0),
                "text": review.get('text', '')
            })
        return result

    def get_directions(self, origin, destination, mode="driving", waypoints=None, alternatives=False):
        """Get directions between two locations
        
        Args:
            origin: Starting location (address or lat,lng)
            destination: Ending location (address or lat,lng)
            mode: Travel mode (driving, walking, bicycling, transit)
            waypoints: List of waypoints to include in the route
            alternatives: Whether to return alternative routes
            
        Returns:
            Dictionary containing directions data
        """
        cache_key = self._cache_key("directions", origin=origin, destination=destination, 
                                    mode=mode, waypoints=str(waypoints), alternatives=str(alternatives))
        
        if cache_key in self.cache:
            cached_data = self.cache[cache_key]
            # Check if cache is still valid (less than 7 days old)
            if datetime.now().timestamp() - cached_data["timestamp"] < 7 * 24 * 3600:
                return cached_data["data"]
        
        # Make API call to directions service
        try:
            url = f"{self.base_url}/directions/json"
            params = {
                "origin": origin,
                "destination": destination,
                "mode": mode,
                "alternatives": str(alternatives).lower(),
                "key": self.api_key
            }
            
            if waypoints:
                params["waypoints"] = "|".join(waypoints)
            
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            # Cache the result
            self.cache[cache_key] = {
                "data": data,
                "timestamp": datetime.now().timestamp()
            }
            self._save_cache()
            
            return data
            
        except Exception as e:
            print(f"Error getting directions: {e}")
            return {"status": "ERROR", "error_message": str(e)}
    
    def get_place_details(self, place_id):
        """Get detailed information about a place
        
        Args:
            place_id: The Google Maps place ID
            
        Returns:
            Dictionary containing place details
        """
        cache_key = self._cache_key("place_details", place_id=place_id)
        
        if cache_key in self.cache:
            cached_data = self.cache[cache_key]
            # Check if cache is still valid (less than 30 days old)
            if datetime.now().timestamp() - cached_data["timestamp"] < 30 * 24 * 3600:
                return cached_data["data"]
        
        # Make API call to place details service
        try:
            url = f"{self.base_url}/place/details/json"
            params = {
                "place_id": place_id,
                "fields": "name,formatted_address,geometry,rating,website,formatted_phone_number,opening_hours,price_level,types,reviews,photos",
                "key": self.api_key
            }
            
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if data['status'] == 'OK':
                result = data['result']
                
                # Format the result for consistency
                formatted_result = {
                    "id": place_id,
                    "name": result.get('name', ''),
                    "address": result.get('formatted_address', ''),
                    "location": result.get('geometry', {}).get('location', {}),
                    "rating": result.get('rating'),
                    "website": result.get('website', ''),
                    "phone": result.get('formatted_phone_number', ''),
                    "price_level": result.get('price_level'),
                    "types": result.get('types', []),
                    "source": "google"
                }
                
                # Format opening hours if available
                if 'opening_hours' in result and 'periods' in result['opening_hours']:
                    opening_hours = {}
                    days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
                    for period in result['opening_hours']['periods']:
                        day_idx = period.get('open', {}).get('day', 0)
                        if day_idx < len(days):
                            day = days[day_idx]
                            open_time = period.get('open', {}).get('time', '')
                            close_time = period.get('close', {}).get('time', '')
                            if open_time and close_time:
                                # Format times from 24hr to 12hr format
                                open_hour = int(open_time[:2])
                                open_suffix = "AM" if open_hour < 12 else "PM"
                                open_hour = open_hour % 12 or 12
                                open_formatted = f"{open_hour}:{open_time[2:]} {open_suffix}"
                                
                                close_hour = int(close_time[:2])
                                close_suffix = "AM" if close_hour < 12 else "PM"
                                close_hour = close_hour % 12 or 12
                                close_formatted = f"{close_hour}:{close_time[2:]} {close_suffix}"
                                
                                opening_hours[day] = f"{open_formatted} – {close_formatted}"
                    
                    formatted_result["opening_hours"] = opening_hours
                
                # Format reviews if available
                if 'reviews' in result:
                    formatted_reviews = []
                    for review in result['reviews']:
                        formatted_review = {
                            "author": review.get('author_name', ''),
                            "rating": review.get('rating', 0),
                            "time": review.get('time', 0),
                            "text": review.get('text', '')
                        }
                        formatted_reviews.append(formatted_review)
                    
                    formatted_result["reviews"] = formatted_reviews
                
                # Format photos if available
                if 'photos' in result:
                    formatted_photos = []
                    for photo in result['photos']:
                        formatted_photo = {
                            "reference": photo.get('photo_reference', ''),
                            "width": photo.get('width', 0),
                            "height": photo.get('height', 0)
                        }
                        formatted_photos.append(formatted_photo)
                    
                    formatted_result["photos"] = formatted_photos
            else:
                formatted_result = {"error": data.get('status'), "message": data.get('error_message', '')}
            
            # Cache the result
            self.cache[cache_key] = {
                "data": formatted_result,
                "timestamp": datetime.now().timestamp()
            }
            self._save_cache()
            
            return formatted_result
            
        except Exception as e:
            print(f"Error getting place details: {e}")
            return {"error": "API_ERROR", "message": str(e)}
    
    def search_places(self, query, location=None, radius=5000, type=None):
        """Search for places based on text query
        
        Args:
            query: Text search string
            location: Center point for nearby search (lat,lng)
            radius: Search radius in meters
            type: Type of place (restaurant, museum, etc.)
            
        Returns:
            List of places matching the search criteria
        """
        cache_key = self._cache_key("places_search", query=query, location=str(location), 
                                    radius=radius, type=type)
        
        if cache_key in self.cache:
            cached_data = self.cache[cache_key]
            # Check if cache is still valid (less than 1 day old)
            if datetime.now().timestamp() - cached_data["timestamp"] < 24 * 3600:
                return cached_data["data"]
        
        # Make API call to places search service
        try:
            url = f"{self.base_url}/place/textsearch/json"
            params = {
                "query": query,
                "key": self.api_key
            }
            
            if location:
                params["location"] = location
                params["radius"] = radius
            
            if type:
                params["type"] = type
            
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if data['status'] == 'OK':
                results = []
                for place in data.get('results', []):
                    formatted_place = {
                        "id": place.get('place_id', ''),
                        "name": place.get('name', ''),
                        "address": place.get('formatted_address', ''),
                        "location": place.get('geometry', {}).get('location', {}),
                        "rating": place.get('rating'),
                        "types": place.get('types', []),
                        "source": "google"
                    }
                    results.append(formatted_place)
            else:
                results = {"error": data.get('status'), "message": data.get('error_message', '')}
            
            # Cache the result
            self.cache[cache_key] = {
                "data": results,
                "timestamp": datetime.now().timestamp()
            }
            self._save_cache()
            
            return results
            
        except Exception as e:
            print(f"Error searching places: {e}")
            return {"error": "API_ERROR", "message": str(e)}
