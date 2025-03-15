import os
import requests
import json
import math
from datetime import datetime

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
    
    def _get_mock_geocode(self, address):
        """Generate mock geocoding data for testing"""
        # Known city coordinates
        city_coords = {
            "paris": {"lat": 48.8566, "lng": 2.3522},
            "london": {"lat": 51.5074, "lng": -0.1278},
            "new york": {"lat": 40.7128, "lng": -74.0060},
            "tokyo": {"lat": 35.6762, "lng": 139.6503},
            "rome": {"lat": 41.9028, "lng": 12.4964},
            "barcelona": {"lat": 41.3851, "lng": 2.1734},
            "berlin": {"lat": 52.5200, "lng": 13.4050},
            "sydney": {"lat": -33.8688, "lng": 151.2093},
            "cairo": {"lat": 30.0444, "lng": 31.2357},
            "los angeles": {"lat": 34.0522, "lng": -118.2437}
        }
        
        # Look for city name in the address
        address_lower = address.lower()
        for city, coords in city_coords.items():
            if city in address_lower:
                return {
                    "address": address,
                    "lat": coords["lat"],
                    "lng": coords["lng"],
                    "formatted_address": address.title()
                }
        
        # If no known city, generate coordinates based on string hash
        address_hash = sum(ord(c) for c in address_lower)
        lat = (address_hash % 180) - 90
        lng = (address_hash * 13 % 360) - 180
        
        return {
            "address": address,
            "lat": lat,
            "lng": lng,
            "formatted_address": address.title()
        }
    
    def get_directions(self, origin, destination, mode="driving"):
        """Get directions between two locations"""
        # Check cache first
        cache_key = self._cache_key("directions", origin=origin.lower(), 
                                   destination=destination.lower(), mode=mode)
        if cache_key in self.cache:
            cached_data = self.cache[cache_key]
            # Check if cache is still valid (less than 7 days old)
            if datetime.now().timestamp() - cached_data["timestamp"] < 7 * 24 * 3600:
                return cached_data["data"]
        
        # If no API key, return mock data
        if not self.api_key:
            result = self._get_mock_directions(origin, destination, mode)
            
            # Cache the result
            self.cache[cache_key] = {
                "data": result,
                "timestamp": datetime.now().timestamp()
            }
            self._save_cache()
            
            return result
        
        # Make API call to directions service
        try:
            url = f"{self.base_url}/directions/json"
            params = {
                "origin": origin,
                "destination": destination,
                "mode": mode,
                "key": self.api_key
            }
            
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if data['status'] == 'OK':
                # Format the response
                route = data['routes'][0]
                leg = route['legs'][0]
                
                result = {
                    "origin": origin,
                    "destination": destination,
                    "distance": {
                        "value": leg['distance']['value'],  # meters
                        "text": leg['distance']['text']
                    },
                    "duration": {
                        "value": leg['duration']['value'],  # seconds
                        "text": leg['duration']['text']
                    },
                    "steps": [self._format_step(step) for step in leg['steps']],
                    "polyline": route['overview_polyline']['points']
                }
            else:
                result = self._get_mock_directions(origin, destination, mode)
            
            # Cache the result
            self.cache[cache_key] = {
                "data": result,
                "timestamp": datetime.now().timestamp()
            }
            self._save_cache()
            
            return result
            
        except Exception as e:
            print(f"Error getting directions: {e}")
            return self._get_mock_directions(origin, destination, mode)
    
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
    
    def _get_mock_directions(self, origin, destination, mode="driving"):
        """Generate mock directions data for testing"""
        # Get mock geocoding for origin and destination
        origin_geo = self._get_mock_geocode(origin)
        dest_geo = self._get_mock_geocode(destination)
        
        # Calculate straight-line distance
        lat1, lon1 = origin_geo['lat'], origin_geo['lng']
        lat2, lon2 = dest_geo['lat'], dest_geo['lng']
        
        # Haversine formula to calculate distance
        R = 6371  # Earth radius in km
        dlon = math.radians(lon2 - lon1)
        dlat = math.radians(lat2 - lat1)
        a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        distance_km = R * c
        
        # Estimate duration based on mode and distance
        speed_km_h = {"driving": 60, "walking": 5, "bicycling": 15, "transit": 40}
        speed = speed_km_h.get(mode, 60)
        duration_hours = distance_km / speed
        
        # Create mock step
        step = {
            "distance": f"{round(distance_km, 1)} km",
            "duration": f"{int(duration_hours * 60)} mins",
            "instructions": f"Travel from {origin} to {destination}",
            "start_location": {"lat": lat1, "lng": lon1},
            "end_location": {"lat": lat2, "lng": lon2}
        }
        
        return {
            "origin": origin,
            "destination": destination,
            "distance": {
                "value": int(distance_km * 1000),  # meters
                "text": f"{round(distance_km, 1)} km"
            },
            "duration": {
                "value": int(duration_hours * 3600),  # seconds
                "text": f"{int(duration_hours * 60)} mins"
            },
            "steps": [step],
            "polyline": "mock_polyline",  # In a real app, would encode the path
            "source": "mock"
        }
    
    def search_places(self, query, location=None, radius=5000, type=None):
        """Search for places based on query and location"""
        # Check cache first
        cache_key = self._cache_key("places", query=query.lower(), 
                                   location=str(location), radius=radius, type=type)
        if cache_key in self.cache:
            cached_data = self.cache[cache_key]
            # Check if cache is still valid (less than 1 day old)
            if datetime.now().timestamp() - cached_data["timestamp"] < 24 * 3600:
                return cached_data["data"]
        
        # If no API key, return mock data
        if not self.api_key:
            result = self._get_mock_places(query, location, radius, type)
            
            # Cache the result
            self.cache[cache_key] = {
                "data": result,
                "timestamp": datetime.now().timestamp()
            }
            self._save_cache()
            
            return result
        
        # Make API call to Places API
        try:
            url = f"{self.base_url}/place/textsearch/json"
            params = {
                "query": query,
                "key": self.api_key
            }
            
            if location:
                if isinstance(location, str):
                    # Convert address to coordinates
                    geo = self.geocode(location)
                    params["location"] = f"{geo['lat']},{geo['lng']}"
                else:
                    # Assumes location is a dict with lat/lng
                    params["location"] = f"{location['lat']},{location['lng']}"
                    
                params["radius"] = radius
            
            if type:
                params["type"] = type
            
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if data['status'] == 'OK':
                places = []
                for place in data['results']:
                    places.append({
                        "id": place['place_id'],
                        "name": place['name'],
                        "address": place.get('formatted_address', ''),
                        "location": {
                            "lat": place['geometry']['location']['lat'],
                            "lng": place['geometry']['location']['lng']
                        },
                        "rating": place.get('rating', 0),
                        "types": place.get('types', []),
                        "price_level": place.get('price_level', 0),
                        "user_ratings_total": place.get('user_ratings_total', 0),
                        "photos": self._format_photos(place.get('photos', []))
                    })
                
                result = {
                    "query": query,
                    "places": places
                }
            else:
                result = self._get_mock_places(query, location, radius, type)
            
            # Cache the result
            self.cache[cache_key] = {
                "data": result,
                "timestamp": datetime.now().timestamp()
            }
            self._save_cache()
            
            return result
            
        except Exception as e:
            print(f"Error searching places: {e}")
            return self._get_mock_places(query, location, radius, type)
    
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
    
    def _get_mock_places(self, query, location=None, radius=5000, type=None):
        """Generate mock places data for testing"""
        query_lower = query.lower()
        place_types = []
        
        if type:
            place_types.append(type)
        
        # Try to infer place types from query
        if "museum" in query_lower:
            place_types.append("museum")
        if "restaurant" in query_lower:
            place_types.append("restaurant")
        if "hotel" in query_lower:
            place_types.append("lodging")
        if "park" in query_lower:
            place_types.append("park")
        
        if not place_types:
            place_types = ["point_of_interest"]
        
        # Generate center location if not provided
        center_lat, center_lng = 48.8566, 2.3522  # Paris by default
        if location:
            if isinstance(location, str):
                geo = self._get_mock_geocode(location)
                center_lat, center_lng = geo['lat'], geo['lng']
            else:
                center_lat = location.get('lat', center_lat)
                center_lng = location.get('lng', center_lng)
        
        # Generate pseudo-random but consistent results based on query
        query_hash = sum(ord(c) for c in query_lower)
        num_results = (query_hash % 5) + 3  # 3-7 results
        
        places = []
        for i in range(num_results):
            # Slightly vary location around center
            offset = 0.01  # ~1km
            lat = center_lat + ((query_hash * (i+1) % 20) - 10) / 1000
            lng = center_lng + ((query_hash * (i+2) % 20) - 10) / 1000
            
            # Generate place name based on query and type
            place_type = place_types[i % len(place_types)]
            
            if "museum" in place_type:
                name = f"{query.title()} {['Museum', 'Gallery', 'Exhibition Center'][i % 3]}"
                price_level = 2
            elif "restaurant" in place_type:
                name = f"{['Café', 'Restaurant', 'Bistro'][i % 3]} {query.title()}"
                price_level = (i % 4) + 1
            elif "lodging" in place_type:
                name = f"{['Hotel', 'Resort', 'Inn'][i % 3]} {query.title()}"
                price_level = (i % 3) + 2
            elif "park" in place_type:
                name = f"{query.title()} {['Park', 'Garden', 'Square'][i % 3]}"
                price_level = 1
            else:
                name = f"{query.title()} {['Place', 'Attraction', 'Site'][i % 3]} #{i+1}"
                price_level = (i % 4) + 1
            
            places.append({
                "id": f"mock_place_{query_hash}_{i}",
                "name": name,
                "address": f"{i+1} {query.title()} Street, City",
                "location": {"lat": lat, "lng": lng},
                "rating": (query_hash % 20 + 30 + i) / 10,  # Rating 3.0-4.9
                "types": [place_type, "point_of_interest"],
                "price_level": price_level,
                "user_ratings_total": (query_hash % 100) * (i + 1),
                "photos": [{"reference": f"mock_photo_{query_hash}_{i}", "width": 400, "height": 300}]
            })
        
        return {
            "query": query,
            "places": places,
            "source": "mock"
        }
    
    def get_place_details(self, place_id):
        """Get detailed information about a specific place"""
        # Check cache first
        cache_key = self._cache_key("place_details", place_id=place_id)
        if cache_key in self.cache:
            cached_data = self.cache[cache_key]
            # Check if cache is still valid (less than 7 days old)
            if datetime.now().timestamp() - cached_data["timestamp"] < 7 * 24 * 3600:
                return cached_data["data"]
        
        # If no API key or mock place ID, return mock data
        if not self.api_key or place_id.startswith("mock_"):
            result = self._get_mock_place_details(place_id)
            
            # Cache the result
            self.cache[cache_key] = {
                "data": result,
                "timestamp": datetime.now().timestamp()
            }
            self._save_cache()
            
            return result
        
        # Make API call to Place Details API
        try:
            url = f"{self.base_url}/place/details/json"
            params = {
                "place_id": place_id,
                "fields": "name,formatted_address,geometry,rating,website,formatted_phone_number," +
                         "opening_hours,price_level,reviews,photos,types",
                "key": self.api_key
            }
            
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if data['status'] == 'OK':
                place = data['result']
                
                result = {
                    "id": place_id,
                    "name": place['name'],
                    "address": place.get('formatted_address', ''),
                    "location": {
                        "lat": place['geometry']['location']['lat'],
                        "lng": place['geometry']['location']['lng']
                    },
                    "rating": place.get('rating', 0),
                    "website": place.get('website', ''),
                    "phone": place.get('formatted_phone_number', ''),
                    "opening_hours": self._format_opening_hours(place.get('opening_hours', {})),
                    "price_level": place.get('price_level', 0),
                    "types": place.get('types', []),
                    "reviews": self._format_reviews(place.get('reviews', [])),
                    "photos": self._format_photos(place.get('photos', []))
                }
            else:
                result = self._get_mock_place_details(place_id)
            
            # Cache the result
            self.cache[cache_key] = {
                "data": result,
                "timestamp": datetime.now().timestamp()
            }
            self._save_cache()
            
            return result
            
        except Exception as e:
            print(f"Error getting place details: {e}")
            return self._get_mock_place_details(place_id)
    
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
    
    def _get_mock_place_details(self, place_id):
        """Generate mock place details for testing"""
        # Parse info from place ID
        parts = place_id.split('_')
        place_type = "point_of_interest"
        query_hash = 0
        index = 0
        
        if len(parts) >= 3:
            if parts[1].isdigit():
                query_hash = int(parts[1])
            if parts[2].isdigit():
                index = int(parts[2])
        
        # Generate consistent mock data based on the place ID
        names = ["Museum", "Restaurant", "Park", "Hotel", "Shop", "Attraction"]
        name = f"{names[query_hash % len(names)]} #{index+1}"
        
        # Generate random but consistent location
        lat = 48.8566 + ((query_hash * (index+1) % 20) - 10) / 1000
        lng = 2.3522 + ((query_hash * (index+2) % 20) - 10) / 1000
        
        # Generate other details
        rating = (query_hash % 20 + 30 + index) / 10  # Rating 3.0-4.9
        price_level = (index % 4) + 1
        
        reviews = []
        for i in range(3):
            reviews.append({
                "author": f"User {query_hash + i}",
                "rating": (query_hash % 5) + 1,
                "time": datetime.now().timestamp() - (i * 86400),  # Days ago
                "text": f"This is a mock review #{i+1} for {name}."
            })
        
        opening_hours = {}
        days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        for day in days:
            if day in ["saturday", "sunday"]:
                opening_hours[day] = "10:00 AM – 4:00 PM"
            else:
                opening_hours[day] = "9:00 AM – 5:00 PM"
        
        return {
            "id": place_id,
            "name": name,
            "address": f"{index+1} Mock Street, Mock City",
            "location": {"lat": lat, "lng": lng},
            "rating": rating,
            "website": "https://example.com",
            "phone": f"+1-555-{query_hash}-{index*1111}",
            "opening_hours": opening_hours,
            "price_level": price_level,
            "types": [place_type],
            "reviews": reviews,
            "photos": [{"reference": f"mock_photo_{query_hash}_{index}", "width": 400, "height": 300}],
            "source": "mock"
        }