import os
import json
import requests
import googlemaps
from dotenv import load_dotenv
from typing import List, Dict, Any, Optional

# Load environment variables from .env file
load_dotenv()

class POIApi:
    def __init__(self, api_key=None):
        """Initialize Points of Interest API with Google Maps client"""
        self.api_key = api_key or os.environ.get("MAPS_API_KEY")
        self.gmaps = googlemaps.Client(key=self.api_key)
    
    def get_poi(self, location, radius=1000, keyword=None, type=None, language="en", min_price=None, max_price=None):
        """
        Search for points of interest near a location
        
        Args:
            location: The latitude/longitude or address to search around
            radius: Distance in meters within which to search
            keyword: Term to search for (e.g. "museum", "restaurant")
            type: Restricts results to places matching the specified type (e.g. "tourist_attraction")
            language: The language in which to return results
            min_price: Minimum price level (0-4)
            max_price: Maximum price level (0-4)
            
        Returns:
            Dictionary containing search results
        """
        params = {
            'location': location,
            'radius': radius,
            'language': language
        }
        
        if keyword:
            params['query'] = keyword  # Changed from 'keyword' to 'query'
        if type:
            params['type'] = type
        if min_price is not None:
            params['min_price'] = min_price
        if max_price is not None:
            params['max_price'] = max_price
            
        return self.gmaps.places(**params)
    
    def get_poi_details(self, place_id, language="en", fields=None):
        """
        Get detailed information about a specific place
        
        Args:
            place_id: The Google Place ID
            language: The language in which to return results
            fields: List of fields to include in the response
            
        Returns:
            Dictionary containing place details
        """
        params = {
            'place_id': place_id,
            'language': language
        }
        
        if fields:
            params['fields'] = fields
            
        return self.gmaps.place(**params)
    
    def get_poi_reviews(self, place_id, language="en", max_reviews=5):
        """
        Get reviews for a specific place
        
        Args:
            place_id: The Google Place ID
            language: The language in which to return results
            max_reviews: Maximum number of reviews to return
            
        Returns:
            Dictionary containing place reviews
        """
        result = self.gmaps.place(
            place_id=place_id,
            language=language,
            fields=['review'],
            reviews_sort="newest"
        )
        
        # Limit the number of reviews returned
        if 'result' in result and 'reviews' in result['result']:
            result['result']['reviews'] = result['result']['reviews'][:max_reviews]
            
        return result
    
    def get_nearby_places(self, location, type, radius=1000, language="en"):
        """
        Find places of a specific type near a location
        
        Args:
            location: The latitude/longitude or address to search around
            type: Type of place to search for (e.g. "restaurant", "museum")
            radius: Distance in meters within which to search
            language: The language in which to return results
            
        Returns:
            List of nearby places
        """
        return self.gmaps.places_nearby(
            location=location,
            radius=radius,
            type=type,
            language=language
        )
    
    def get_distance_matrix(self, origins, destinations, mode="driving", language="en", units="metric"):
        """
        Calculate distance and duration between multiple origins and destinations
        
        Args:
            origins: List of addresses or lat/lng values
            destinations: List of addresses or lat/lng values
            mode: Travel mode (driving, walking, bicycling, transit)
            language: The language in which to return results
            units: Unit system for distances (metric, imperial)
            
        Returns:
            Distance matrix results
        """
        return self.gmaps.distance_matrix(
            origins=origins,
            destinations=destinations,
            mode=mode,
            language=language,
            units=units
        )
    
    def get_place_photos(self, photo_reference, max_width=400, max_height=400):
        """
        Get photos for a place
        
        Args:
            photo_reference: Photo reference from a Place Search or Details response
            max_width: Maximum width of the image
            max_height: Maximum height of the image
            
        Returns:
            URL to the photo
        """
        return self.gmaps.places_photo(
            photo_reference=photo_reference,
            max_width=max_width,
            max_height=max_height
        )
class InformationAgent:
    def __init__(self, api_key=None):
        """Initialize InformationAgent with API key for external services"""
        self.api_key = api_key or os.environ.get("MAPS_API_KEY")  # Changed from GOOGLE_MAPS_API_KEY to MAPS_API_KEY
        self.attractions_cache = {}
        self.poi_api = POIApi(self.api_key)
        
    def get_attractions(self, city):
        """Get attractions for a specific city"""
        # Check if we have cached data first
        if city in self.attractions_cache:
            return self.attractions_cache[city]
        
        # Try to load from local data file
        try:
            with open("data/attractions.json", "r", encoding="utf-8") as f:
                all_attractions = json.load(f)
                if city in all_attractions:
                    self.attractions_cache[city] = all_attractions[city]
                    return all_attractions[city]
        except (FileNotFoundError, json.JSONDecodeError):
            pass  # File doesn't exist or is invalid, continue to API
        
        # Fetch from external API if local data not available
        attractions = self._fetch_attractions_from_api(city)
        
        # Cache the results
        self.attractions_cache[city] = attractions
        return attractions
    
    def _fetch_attractions_from_api(self, city):
        """Fetch attractions from external API using Google Places API"""
        try:
            # Get initial list of places
            places_result = self.poi_api.get_poi(city, radius=5000, keyword="tourist attraction")
            attractions = []
            
            # Process up to 20 attractions
            for place in places_result.get("results", [])[:20]:
                # Get additional details for each place
                place_details = self.poi_api.get_poi_details(place["place_id"])["result"]
                
                # Get opening hours
                opening_hours = place_details.get("opening_hours", {}).get("weekday_text", [])
                
                # Get reviews
                reviews_data = self.poi_api.get_poi_reviews(place["place_id"])
                reviews = reviews_data.get("result", {}).get("reviews", [])[:5]
                
                attraction = {
                    "id": place["place_id"],
                    "name": place["name"],
                    "address": place.get("formatted_address", place.get("vicinity","")),
                    "rating": place.get("rating", 0),
                    "category": self._guess_category(place),
                    "location": {
                        "lat": place["geometry"]["location"]["lat"],
                        "lng": place["geometry"]["location"]["lng"]
                    },
                    "opening_hours": opening_hours,
                    "estimated_duration": self._estimate_visit_duration(place),
                    "price_level": place.get("price_level", 2),
                    "photos": place_details.get("photos",[]),
                    "reviews": reviews
                }
                attractions.append(attraction)
            
            # Save to local file for future use
            self._save_attractions_to_file(city, attractions)
            
            return attractions
                
        except Exception as e:
            print(f"Error fetching attractions: {e}")
            return []
    
    def _guess_category(self, place):
        """Guess the category of an attraction from its types"""
        types = place.get("types", [])
        
        if "museum" in types:
            return "museum"
        elif "park" in types:
            return "nature"
        elif "amusement_park" in types:
            return "entertainment"
        elif "landmark" in types or "tourist_attraction" in types:
            return "landmark"
        elif "restaurant" in types or "cafe" in types:
            return "dining"
        elif "shopping_mall" in types or "store" in types:
            return "shopping"
        else:
            return "other"
    
    def _estimate_visit_duration(self, place):
        """Estimate how long a visit might take based on place type"""
        types = place.get("types", [])
        
        if "museum" in types:
            return 3  # 3 hours for museums
        elif "park" in types:
            return 2  # 2 hours for parks
        elif "amusement_park" in types:
            return 5  # 5 hours for amusement parks
        elif "landmark" in types:
            return 1.5  # 1.5 hours for landmarks
        else:
            return 2  # Default 2 hours
    
    def _save_attractions_to_file(self, city, attractions):
        """Save attractions data to local file"""
        try:
            # Create data directory if it doesn't exist
            os.makedirs("data", exist_ok=True)
            
            # Load existing data if available
            try:
                with open("data/attractions.json", "r", encoding="utf-8") as f:
                    all_attractions = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                all_attractions = {}
            
            # Update with new data
            all_attractions[city] = attractions
            
            # Save back to file
            with open("data/attractions.json", "w", encoding="utf-8") as f:
                json.dump(all_attractions, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            print(f"Error saving attractions data: {e}")
