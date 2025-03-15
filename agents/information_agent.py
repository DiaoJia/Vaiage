import os
import json
import requests

class InformationAgent:
    def __init__(self, api_key=None):
        """Initialize InformationAgent with API key for external services"""
        self.api_key = api_key or os.environ.get("MAPS_API_KEY")
        self.attractions_cache = {}
        
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
        # This is a placeholder for real API implementation
        attractions = self._fetch_attractions_from_api(city)
        
        # Cache the results
        self.attractions_cache[city] = attractions
        return attractions
    
    def _fetch_attractions_from_api(self, city):
        """Fetch attractions from external API"""
        # This is a placeholder - you would implement actual API calls here
        # For example, using Google Places API or similar
        
        # Mock implementation for testing
        try:
            response = requests.get(
                f"https://maps.googleapis.com/maps/api/place/textsearch/json",
                params={
                    "query": f"attractions in {city}",
                    "key": self.api_key
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                attractions = []
                
                for place in data.get("results", [])[:20]:  # Limit to 20 attractions
                    attractions.append({
                        "id": place.get("place_id"),
                        "name": place.get("name"),
                        "address": place.get("formatted_address"),
                        "rating": place.get("rating", 0),
                        "category": self._guess_category(place),
                        "location": {
                            "lat": place["geometry"]["location"]["lat"],
                            "lng": place["geometry"]["location"]["lng"]
                        },
                        "opening_hours": self._get_opening_hours(place.get("place_id")),
                        "estimated_duration": 2,  # Default 2 hours
                        "price_level": place.get("price_level", 2)
                    })
                
                return attractions
                
        except Exception as e:
            print(f"Error fetching attractions: {e}")
        
        # Fallback to mock data
        return self._get_mock_attractions(city)
    
    def _get_opening_hours(self, place_id):
        """Get detailed opening hours for a place"""
        # This would be implemented with Place Details API
        # Mock implementation for now
        return {
            "monday": "9:00 AM - 5:00 PM",
            "tuesday": "9:00 AM - 5:00 PM",
            "wednesday": "9:00 AM - 5:00 PM",
            "thursday": "9:00 AM - 5:00 PM",
            "friday": "9:00 AM - 5:00 PM",
            "saturday": "10:00 AM - 4:00 PM",
            "sunday": "10:00 AM - 4:00 PM"
        }
    
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
        else:
            return "other"
    
    def _get_mock_attractions(self, city):
        """Generate mock attractions data for testing"""
        if city.lower() == "paris":
            return [
                {
                    "id": "eiffel_tower",
                    "name": "Eiffel Tower",
                    "address": "Champ de Mars, 5 Avenue Anatole France, 75007 Paris",
                    "rating": 4.6,
                    "category": "landmark",
                    "location": {"lat": 48.8584, "lng": 2.2945},
                    "opening_hours": {"monday": "9:00 AM - 11:45 PM"},
                    "estimated_duration": 3,
                    "price_level": 3
                },
                {
                    "id": "louvre_museum",
                    "name": "Louvre Museum",
                    "address": "Rue de Rivoli, 75001 Paris",
                    "rating": 4.7,
                    "category": "museum",
                    "location": {"lat": 48.8606, "lng": 2.3376},
                    "opening_hours": {"monday": "9:00 AM - 6:00 PM"},
                    "estimated_duration": 4,
                    "price_level": 2
                },
                {
                    "id": "notre_dame",
                    "name": "Notre-Dame Cathedral",
                    "address": "6 Parvis Notre-Dame - Pl. Jean-Paul II, 75004 Paris",
                    "rating": 4.7,
                    "category": "landmark",
                    "location": {"lat": 48.8530, "lng": 2.3499},
                    "opening_hours": {"monday": "8:00 AM - 6:45 PM"},
                    "estimated_duration": 2,
                    "price_level": 1
                },
                {
                    "id": "arc_de_triomphe",
                    "name": "Arc de Triomphe",
                    "address": "Place Charles de Gaulle, 75008 Paris",
                    "rating": 4.7,
                    "category": "landmark",
                    "location": {"lat": 48.8738, "lng": 2.2950},
                    "opening_hours": {"monday": "10:00 AM - 10:30 PM"},
                    "estimated_duration": 1,
                    "price_level": 2
                },
                {
                    "id": "montmartre",
                    "name": "Montmartre",
                    "address": "75018 Paris",
                    "rating": 4.6,
                    "category": "landmark",
                    "location": {"lat": 48.8867, "lng": 2.3431},
                    "opening_hours": {"monday": "Open 24 hours"},
                    "estimated_duration": 3,
                    "price_level": 1
                }
            ]
        elif city.lower() == "new york":
            return [
                {
                    "id": "statue_of_liberty",
                    "name": "Statue of Liberty",
                    "category": "landmark",
                    "location": {"lat": 40.6892, "lng": -74.0445},
                    "estimated_duration": 4,
                    "price_level": 3
                },
                {
                    "id": "central_park",
                    "name": "Central Park",
                    "category": "nature",
                    "location": {"lat": 40.7812, "lng": -73.9665},
                    "estimated_duration": 3,
                    "price_level": 0
                },
                {
                    "id": "empire_state_building",
                    "name": "Empire State Building",
                    "category": "landmark",
                    "location": {"lat": 40.7484, "lng": -73.9857},
                    "estimated_duration": 2,
                    "price_level": 3
                },
                {
                    "id": "metropolitan_museum_of_art",
                    "name": "Metropolitan Museum of Art",
                    "category": "museum",
                    "location": {"lat": 40.7794, "lng": -73.9632},
                    "estimated_duration": 4,
                    "price_level": 2
                },
                {
                    "id": "times_square",
                    "name": "Times Square",
                    "category": "landmark",
                    "location": {"lat": 40.7580, "lng": -73.9855},
                    "estimated_duration": 2,
                    "price_level": 0
                }
            ]
        else:
            # Generic attractions for any other city
            return [
                {
                    "id": f"{city}_museum_1",
                    "name": f"{city} Museum of Art",
                    "category": "museum",
                    "location": {"lat": 0, "lng": 0},
                    "estimated_duration": 3,
                    "price_level": 2
                },
                {
                    "id": f"{city}_park_1",
                    "name": f"{city} Central Park",
                    "category": "nature",
                    "location": {"lat": 0, "lng": 0},
                    "estimated_duration": 2,
                    "price_level": 0
                },
                {
                    "id": f"{city}_landmark_1",
                    "name": f"{city} Famous Tower",
                    "category": "landmark",
                    "location": {"lat": 0, "lng": 0},
                    "estimated_duration": 2,
                    "price_level": 2
                },
                {
                    "id": f"{city}_historic_1",
                    "name": f"{city} Historic District",
                    "category": "landmark",
                    "location": {"lat": 0, "lng": 0},
                    "estimated_duration": 3,
                    "price_level": 0
                },
                {
                    "id": f"{city}_market_1",
                    "name": f"{city} Market Square",
                    "category": "shopping",
                    "location": {"lat": 0, "lng": 0},
                    "estimated_duration": 2,
                    "price_level": 1
                }
            ]