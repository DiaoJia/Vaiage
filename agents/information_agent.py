import os
import sys
import json
import googlemaps
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from datetime import datetime

# Add the parent directory to sys.path to allow imports from services
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.maps_api import POIApi
from services.weather_api import WeatherService
from services.car_rental_api import CarRentalService


def format_duration(seconds):
    if seconds is None:
        return "N/A"
    minutes, sec = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    duration_str = ""
    if hours > 0:
        duration_str += f"{hours} hour{'s' if hours > 1 else ''} "
    if minutes > 0:
        duration_str += f"{minutes} min{'s' if minutes > 1 else ''}"
    if not duration_str: # Handle cases less than a minute
         duration_str = f"{sec} sec{'s' if sec > 1 else ''}"
    return duration_str.strip()

# --- Helper function for formatting distance ---
def format_distance(meters):
    if meters is None:
        return "N/A"
    km = meters / 1000.0
    miles = meters / 1609.34
    return f"{km:.1f} km / {miles:.1f} miles"

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
        agent = InformationAgent()
        
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
        #nearby places
        nearby = agent.search_nearby_places(lat=37.8715, lng=-122.2730, radius=500)
    """
    def __init__(self, maps_api_key=None, car_api_key=None):
        """Initialize InformationAgent with optional API keys"""
        # Initialize Google Maps API
        self.maps_api_key = maps_api_key or os.getenv("MAPS_API_KEY")
        self.rapidapi_key = car_api_key or os.getenv("RAPIDAPI_KEY")
        
        self.gmaps = googlemaps.Client(key=self.maps_api_key)
        self.poi_api = POIApi(self.maps_api_key)
        self.weather_service = WeatherService()
        # Car rental service
        self.car_rental_service = None
        if self.rapidapi_key:
            self.car_rental_service = CarRentalService(rapidapi_key=self.rapidapi_key)
        #nearby places
        self.nearby_places = {}

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
        Route Planning (Simple A to B for multiple modes).

        Input:
            - origin: Starting point (address, place name, or lat/lng tuple/dict)
            - destination: End point (address, place name, or lat/lng tuple/dict)

        Output Format:
            List[Dict[str, Any]] or empty list. Each dict represents a travel mode:
            [
                {
                    'mode': str,                # e.g., 'driving', 'transit'
                    'distance': str,            # Formatted distance text (e.g., "10.2 miles")
                    'duration': str,            # Formatted duration text (e.g., "25 mins")
                    'distance_meters': int,     # Raw distance in meters
                    'duration_seconds': int,    # Raw duration in seconds
                    'fare': str | None          # Estimated fare text (mostly for transit)
                },
                ...
            ]
        """
        modes = ['driving', 'walking', 'bicycling', 'transit']
        routes = []
        for mode in modes:
            try:
                # Keep 'en' for consistent address resolution and international compatibility
                directions = self.gmaps.directions(
                    origin, destination, mode=mode, language='en'
                )
                if not directions:
                    continue

                # Ensure legs exist and are not empty
                if not directions[0].get('legs'):
                    print(f"Warning: Route for mode '{mode}' from '{origin}' to '{destination}' lacks 'legs' data.")
                    continue
                leg = directions[0]['legs'][0]

                # Ensure distance and duration exist in the leg
                if 'distance' not in leg or 'duration' not in leg:
                     print(f"Warning: Leg for mode '{mode}' from '{origin}' to '{destination}' lacks distance or duration data.")
                     continue

                info = {
                    'mode': mode,
                    'distance': leg['distance']['text'],
                    'duration': leg['duration']['text'],
                    'distance_meters': leg['distance']['value'], # Raw distance in meters
                    'duration_seconds': leg['duration']['value']  # Raw duration in seconds
                }
                # Add fare info if available
                if 'fare' in directions[0]:
                    info['fare'] = directions[0]['fare'].get('text')
                routes.append(info)
            except googlemaps.exceptions.ApiError as e:
                 print(f"Error planning route for mode '{mode}' from '{origin}' to '{destination}': {e}")
            except IndexError:
                 print(f"Index error processing route result for mode '{mode}' from '{origin}' to '{destination}' (likely missing 'legs').")
            except KeyError as e:
                 print(f"Key error processing route result for mode '{mode}' from '{origin}' to '{destination}': {e} (likely missing 'distance' or 'duration').")
            except Exception as e:
                 print(f"An unexpected error occurred during route planning for mode '{mode}': {e}")
        return routes

    def plan_with_waypoints(self, origin: str, destination: str, waypoints: list,
                                            mode: str = 'driving', departure_time: datetime = None):
        """
        Plans an optimized route visiting a list of waypoints between an origin and destination.
        Uses the Google Maps Directions API with waypoint optimization (`optimize_waypoints=True`).

        Input:
            - origin: Starting point (address, place name, or lat/lng tuple/dict)
            - destination: End point (address, place name, or lat/lng tuple/dict)
            - waypoints: List of intermediate points (list of strings, lat/lng tuples/dicts)
            - mode: Travel mode (default: 'driving'). Optimization works best for 'driving'.
            - departure_time: Optional datetime object (default: now) for traffic estimation.

        Output Format:
            Dict[str, Any] or None if no route is found.
            {
                'path_sequence': List[str],         # List of addresses in optimized order (Origin, WptX, WptY,..., Dest)
                'waypoint_original_indices': List[int], # Order original waypoints were visited (0-based index)
                'total_duration_text': str,         # Formatted total duration (e.g., "2 hours 30 mins")
                'total_duration_seconds': int,      # Raw total duration in seconds
                'total_duration_in_traffic_text': str | None, # Formatted duration with traffic (if available)
                'total_duration_in_traffic_seconds': int | None, # Raw duration with traffic (if available)
                'total_distance_text': str,         # Formatted total distance (e.g., "150.5 km / 93.5 miles")
                'total_distance_meters': int,       # Raw total distance in meters
                'fare': str | None                  # Estimated fare text (rare for driving)
            }
        """
        # Handle empty waypoints list by falling back to simple A-B route planning
        if not waypoints:
            print("Warning: No waypoints provided. Calling standard plan_routes for A-B.")
            simple_route_options = self.plan_routes(origin, destination)
            # Find the driving route from the simple options
            driving_route = next((r for r in simple_route_options if r['mode'] == 'driving'), None)
            if driving_route:
                 # Addresses from API are resolved; use original input if unavailable in fallback
                 start_addr = origin if isinstance(origin, str) else f"Coord: {origin}"
                 end_addr = destination if isinstance(destination, str) else f"Coord: {destination}"
                 return {
                    'path_sequence': [start_addr, end_addr], # Simplified path
                    'waypoint_original_indices': [],
                    'total_duration_text': driving_route['duration'],
                    'total_duration_seconds': driving_route['duration_seconds'],
                    'total_duration_in_traffic_text': None, # Not available from simple plan_routes call here
                    'total_duration_in_traffic_seconds': None,
                    'total_distance_text': driving_route['distance'],
                    'total_distance_meters': driving_route['distance_meters'],
                    'fare': driving_route.get('fare')
                 }
            else:
                print(f"Could not find a driving route from {origin} to {destination} in fallback.")
                return None

        # Set departure time to now if not specified
        if departure_time is None:
            departure_time = datetime.now()

        print(f"Planning optimized route: {origin} -> Waypoints -> {destination} for mode '{mode}'")

        try:
            # Call Google Maps Directions API
            # language='en' affects instruction text, addresses usually resolve globally
            directions_result = self.gmaps.directions(
                origin,
                destination,
                waypoints=waypoints,
                optimize_waypoints=True, # <<< Key parameter for optimization
                mode=mode,
                departure_time=departure_time,
                language='en'
            )

            # Check if API returned a valid result
            if not directions_result:
                print("No route found for the given points and mode.")
                return None

            # Get the first recommended route
            route = directions_result[0]
            # 'legs' are the segments between points (origin->wpt1, wpt1->wpt2, ..., wptN->dest)
            legs = route['legs']

            # Calculate total duration and distance by summing up values from each leg
            total_duration_sec = sum(leg['duration']['value'] for leg in legs)
            total_distance_m = sum(leg['distance']['value'] for leg in legs)

            # Calculate duration with traffic if available for all legs
            total_duration_traffic_sec = None
            if all('duration_in_traffic' in leg for leg in legs):
                 total_duration_traffic_sec = sum(leg['duration_in_traffic']['value'] for leg in legs)

            # Reconstruct the path sequence using resolved addresses from the API response
            # Start address is from the first leg; end addresses are from each leg
            path_sequence = [legs[0]['start_address']] + [leg['end_address'] for leg in legs]

            # Get the optimized order of the *original* waypoints list (0-based indices)
            optimized_indices = route.get('waypoint_order', [])

            # Prepare the result dictionary
            result = {
                'path_sequence': path_sequence,
                'waypoint_original_indices': optimized_indices,
                'total_duration_text': format_duration(total_duration_sec),
                'total_duration_seconds': total_duration_sec,
                'total_distance_text': format_distance(total_distance_m),
                'total_distance_meters': total_distance_m,
                'fare': route.get('fare', {}).get('text') # Extract fare text if present
            }

            # Add traffic duration details if calculated
            if total_duration_traffic_sec is not None:
                result['total_duration_in_traffic_text'] = format_duration(total_duration_traffic_sec)
                result['total_duration_in_traffic_seconds'] = total_duration_traffic_sec
            else:
                 result['total_duration_in_traffic_text'] = None
                 result['total_duration_in_traffic_seconds'] = None

            return result

        # Handle potential API errors or other exceptions
        except googlemaps.exceptions.ApiError as e:
            print(f"Error planning optimized route: {e}")
            return None
        except Exception as e:
            print(f"An unexpected error occurred during optimized route planning: {e}")
            # Optionally re-raise or log the full traceback for debugging
            # import traceback
            # traceback.print_exc()
            return None

    def get_weather(self, lat: float, lng: float, start_date: str, duration: int, summary: bool = True):
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
        # Get detailed weather data first
        weather_data = self.weather_service.get_weather(lat, lng, start_date, duration)
        
        # If no weather data, return empty result
        if not weather_data:
            return {'detailed_forecast': [], 'summary': None}
        
        # Create result dictionary with detailed forecast
        result = {
            'detailed_forecast': weather_data,
            'summary': None
        }
        
        # Generate summary if requested
        if summary:
            # Create a prompt for the summary writer
            weather_info = json.dumps(weather_data, indent=2)
            prompt = f"""
            Summarize the following weather forecast in a concise paragraph (max 100 words).
            Include key information about temperature ranges, precipitation, and any notable weather conditions.
            Also mention any precautions travelers should take based on the forecast.
            
            Weather data:
            {weather_info}
            """
            
            # Generate the summary
            messages = [
                SystemMessage(content="You are a helpful weather assistant that provides concise summaries of weather forecasts for travelers."),
                HumanMessage(content=prompt)
            ]
            
            # Add the summary to the result
            result['summary'] = self.weather_summary_writer.invoke(messages)
        
        return result
            
        
    def search_car_rentals(self, location: str, start_date: str, end_date: str,
                           driver_age: int = 30, min_price: float = None, 
                           max_price: float = None, top_n: int = 5):
        """
        Car Rental Search:
        
        Input:
            - location: Location
            - start_date: Pickup date
            - end_date: Return date
            - driver_age: Driver's age (default: 30)
            - min_price: Minimum price (optional)
            - max_price: Maximum price (optional)
            - top_n: Number of results to return (default: 5)
            
        Output:
            Top N car rental options, including car type, price, pickup/return locations, links, etc.
            
        Example:
            [
                {
                    "car_model": "Mitsubishi Mirage",
                    "car_group": "Economy",
                    "price": 332.29,
                    "currency": "USD",
                    "pickup_location_name": "Los Angeles International Airport",
                    "supplier_name": "Enterprise",
                    "image_url": "https://cdn.rcstatic.com/images/car_images/web/mitsubishi/mirage_lrg.png"
                },
                ...
            ]
        """
        try:
            # Get location coordinates
            location_data = self.city2geocode(location)
            if not location_data:
                return self._get_mock_car_data(top_n)
            
            # Parse dates
            pickup_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
            dropoff_date_obj = datetime.strptime(end_date, "%Y-%m-%d")
            
            # Format dates and times for API
            pickup_date = pickup_date_obj.strftime("%Y-%m-%d")
            pickup_time = "10:00:00"  # Default pickup time
            dropoff_date = dropoff_date_obj.strftime("%Y-%m-%d")
            dropoff_time = "10:00:00"  # Default dropoff time
            
            # Call the car rental service
            cars = self.car_rental_service.find_available_cars(
                pickup_lat=location_data['lat'],
                pickup_lon=location_data['lng'],
                pickup_date=pickup_date,
                pickup_time=pickup_time,
                dropoff_lat=location_data['lat'],
                dropoff_lon=location_data['lng'],
                dropoff_date=dropoff_date,
                dropoff_time=dropoff_time,
                currency_code="USD",
                driver_age=driver_age,
                pickup_city=location,
                dropoff_city=location,
                pickup_loc_name=location
            )
            
            # Filter by price if needed
            if cars and min_price is not None:
                cars = [c for c in cars if c.get('price', 0) >= min_price]
            if cars and max_price is not None:
                cars = [c for c in cars if c.get('price', 0) <= max_price]
                
            # Return top N results
            return cars[:top_n] if cars else self._get_mock_car_data(top_n)
            
        except Exception as e:
            print(f"Error in search_car_rentals: {str(e)}")
            return self._get_mock_car_data(top_n)
            
    # you could delete this function if the car rental service is working
    def _get_mock_car_data(self, top_n: int = 5):
        
        mock_cars = [
            {
                "car_model": "Toyota Corolla",
                "car_group": "Economy",
                "price": 299.99,
                "currency": "USD",
                "pickup_location_name": "Sample Airport",
                "supplier_name": "Hertz",
                "image_url": "https://example.com/corolla.jpg"
            },
            {
                "car_model": "Honda Civic",
                "car_group": "Compact",
                "price": 349.99,
                "currency": "USD",
                "pickup_location_name": "Sample Airport",
                "supplier_name": "Avis",
                "image_url": "https://example.com/civic.jpg"
            },
            {
                "car_model": "Ford Mustang",
                "car_group": "Sports",
                "price": 599.99,
                "currency": "USD",
                "pickup_location_name": "Sample Airport",
                "supplier_name": "Enterprise",
                "image_url": "https://example.com/mustang.jpg"
            },
            {
                "car_model": "BMW 3 Series",
                "car_group": "Luxury",
                "price": 799.99,
                "currency": "USD",
                "pickup_location_name": "Sample Airport",
                "supplier_name": "Sixt",
                "image_url": "https://example.com/bmw.jpg"
            },
            {
                "car_model": "Mercedes-Benz C-Class",
                "car_group": "Premium",
                "price": 899.99,
                "currency": "USD",
                "pickup_location_name": "Sample Airport",
                "supplier_name": "Europcar",
                "image_url": "https://example.com/mercedes.jpg"
            }
        ]
        return mock_cars[:top_n]

    def search_nearby_places(self, lat: float, lng: float, radius: int = 500):
        """Search for nearby restaurants
        
        Args:
            lat (float): Latitude
            lng (float): Longitude
            radius (int): Search radius (meters)
        
        Returns:
            dict: Dictionary containing information about nearby restaurants
        """
        try:
            # Check if POI API is available
            if not self.poi_api:
                raise Exception("POI API is not initialized")

            # Search for nearby restaurants
            restaurants_result = self.poi_api.get_nearby_places(
                location=(lat, lng),
                type='restaurant',
                radius=radius
            )
            
            # Process restaurant information
            processed_restaurants = []
            for place in restaurants_result.get('results', [])[:5]:  # Only take the first 5 results
                try:
                    # Get detailed information
                    place_details = self.poi_api.get_poi_details(
                        place_id=place['place_id'],
                        fields=['name', 'rating', 'price_level', 'formatted_address', 'photo', 'type', 'geometry']
                    )
                    
                    if not place_details or 'result' not in place_details:
                        continue
                        
                    place_details = place_details['result']
                    
                    # Get photos
                    photos = []
                    if 'photos' in place:  # Get photo info from the original search result
                        for photo in place['photos'][:3]:  # Up to 3 photos
                            photo_url = f"https://maps.googleapis.com/maps/api/place/photo?maxwidth=800&photoreference={photo['photo_reference']}&key={self.maps_api_key}"
                            photos.append({
                                'url': photo_url,
                                'width': photo.get('width', 800),
                                'height': photo.get('height', 600)
                            })
                    
                    restaurant = {
                        'name': place_details.get('name', 'Unknown Restaurant'),
                        'type': 'restaurant',
                        'rating': place_details.get('rating', 0),
                        'price_level': place_details.get('price_level', 0),
                        'address': place_details.get('formatted_address', 'Unknown address'),
                        'photos': photos,
                        'features': self._get_restaurant_features(place)  # Use type info from the original search result
                    }
                    processed_restaurants.append(restaurant)
                except Exception as e:
                    print(f"Error processing restaurant info: {str(e)}")
                    continue
            
            return {
                'restaurants': processed_restaurants
            }
            
        except Exception as e:
            print(f"Error searching nearby places: {str(e)}")
            # Return mock data
            return {
                'restaurants': [
                    {
                        'name': 'Sample Restaurant',
                        'type': 'restaurant',
                        'rating': 4.5,
                        'price_level': 2,
                        'address': 'Sample Address',
                        'photos': [
                            {
                                'url': 'https://example.com/photo1.jpg',
                                'width': 800,
                                'height': 600
                            }
                        ],
                        'features': 'Cuisine: Chinese, Western'
                    }
                ]
            }
    
    def _get_restaurant_features(self, place):
        """Get restaurant features info"""
        features = []
        if 'types' in place:
            if 'chinese_restaurant' in place['types']:
                features.append('Chinese')
            if 'japanese_restaurant' in place['types']:
                features.append('Japanese')
            if 'italian_restaurant' in place['types']:
                features.append('Italian')
            if 'french_restaurant' in place['types']:
                features.append('French')
        return ', '.join(features) if features else 'Cuisine'

