import os
import requests
import json
from datetime import datetime, timedelta
import random

class CarRentalService:
    def __init__(self, api_key=None):
        """Initialize the car rental service with API key"""
        self.api_key = api_key or os.environ.get("CAR_RENTAL_API_KEY")
        self.base_url = "https://api.carrental.example.com/v1"  # Placeholder URL
        self.cache_file = "data/car_rental_cache.json"
        self.cache = self._load_cache()
    
    def _load_cache(self):
        """Load car rental cache from file"""
        try:
            with open(self.cache_file, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
    
    def _save_cache(self):
        """Save car rental cache to file"""
        os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
        with open(self.cache_file, 'w') as f:
            json.dump(self.cache, f)
    
    def _cache_key(self, location, start_date, end_date, vehicle_type=None):
        """Generate a cache key for car rental search"""
        vehicle_str = f"_{vehicle_type}" if vehicle_type else ""
        return f"{location.lower()}_{start_date}_{end_date}{vehicle_str}"
    
    def search_available_cars(self, location, start_date, end_date, vehicle_type=None):
        """Search for available cars at a location and date range"""
        # Check cache first
        cache_key = self._cache_key(location, start_date, end_date, vehicle_type)
        if cache_key in self.cache:
            cached_data = self.cache[cache_key]
            # Check if cache is still valid (less than 1 hour old)
            if datetime.now().timestamp() - cached_data["timestamp"] < 3600:
                return cached_data["data"]
        
        # If no API key or using a mock service, return mock data
        if not self.api_key:
            result = self._get_mock_available_cars(location, start_date, end_date, vehicle_type)
            
            # Cache the result
            self.cache[cache_key] = {
                "data": result,
                "timestamp": datetime.now().timestamp()
            }
            self._save_cache()
            
            return result
        
        # Make API call to car rental service
        try:
            url = f"{self.base_url}/search"
            params = {
                "location": location,
                "pickup_date": start_date,
                "return_date": end_date,
                "api_key": self.api_key
            }
            
            if vehicle_type:
                params["vehicle_type"] = vehicle_type
            
            response = requests.get(url, params=params)
            response.raise_for_status()
            result = response.json()
            
            # Cache the result
            self.cache[cache_key] = {
                "data": result,
                "timestamp": datetime.now().timestamp()
            }
            self._save_cache()
            
            return result
            
        except Exception as e:
            print(f"Error fetching car rental data: {e}")
            return self._get_mock_available_cars(location, start_date, end_date, vehicle_type)
    
    def _get_mock_available_cars(self, location, start_date, end_date, vehicle_type=None):
        """Generate mock car rental data for testing"""
        # Calculate number of days
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        days = (end - start).days
        
        # Generate a pseudo-random but consistent result based on parameters
        location_hash = sum(ord(c) for c in location.lower())
        date_hash = sum(ord(c) for c in start_date)
        combined_hash = (location_hash + date_hash) % 100
        
        # Number of available cars depends on location and dates
        num_cars = max(3, 10 - (combined_hash % 7))
        
        # Define car types
        car_types = ["economy", "compact", "midsize", "standard", "fullsize", "premium", "suv", "minivan"]
        if vehicle_type:
            car_types = [t for t in car_types if t == vehicle_type.lower()]
        
        # Base daily rates by car type
        base_rates = {
            "economy": 25,
            "compact": 30,
            "midsize": 35,
            "standard": 40,
            "fullsize": 45,
            "premium": 60,
            "suv": 55,
            "minivan": 65
        }
        
        # City-specific price factors
        city_factors = {
            "paris": 1.2,
            "london": 1.3,
            "new york": 1.4,
            "tokyo": 1.5,
            "rome": 1.1,
            "barcelona": 1.0
        }
        
        # Find the best matching city factor
        city_factor = 1.0
        for city, factor in city_factors.items():
            if city in location.lower():
                city_factor = factor
                break
        
        # Season factor (high season = higher prices)
        month = start.month
        season_factor = 1.0 + abs(((month - 1) % 12) - 6) / 10  # Higher in Jun/Jul/Dec/Jan
        
        # Generate available cars
        available_cars = []
        for i in range(min(num_cars, len(car_types))):
            car_type = car_types[i % len(car_types)]
            base_rate = base_rates[car_type]
            
            # Apply factors and some randomization
            daily_rate = round(base_rate * city_factor * season_factor * (0.9 + (combined_hash % 30) / 100), 2)
            total_price = round(daily_rate * days, 2)
            
            available_cars.append({
                "id": f"{car_type}_{location_hash}_{i}",
                "vehicle_type": car_type,
                "make": self._get_mock_car_make(car_type),
                "model": self._get_mock_car_model(car_type),
                "year": 2020 + (combined_hash % 5),
                "daily_rate": daily_rate,
                "total_price": total_price,
                "location": {
                    "pickup": location,
                    "dropoff": location
                },
                "dates": {
                    "pickup": start_date,
                    "dropoff": end_date
                },
                "features": self._get_mock_car_features(car_type),
                "availability": "available"
            })
        
        return {
            "location": location,
            "search_dates": {
                "start": start_date,
                "end": end_date
            },
            "available_cars": available_cars,
            "source": "mock"
        }
    
    def _get_mock_car_make(self, car_type):
        """Get a mock car make based on car type"""
        makes_by_type = {
            "economy": ["Toyota", "Honda", "Nissan", "Kia"],
            "compact": ["Toyota", "Honda", "Mazda", "Ford"],
            "midsize": ["Toyota", "Honda", "Hyundai", "Volkswagen"],
            "standard": ["Toyota", "Honda", "Nissan", "Volkswagen"],
            "fullsize": ["Toyota", "Ford", "Chevrolet", "Nissan"],
            "premium": ["BMW", "Audi", "Mercedes-Benz", "Lexus"],
            "suv": ["Toyota", "Honda", "Ford", "Jeep", "Chevrolet"],
            "minivan": ["Toyota", "Honda", "Chrysler", "Kia"]
        }
        
        makes = makes_by_type.get(car_type, ["Toyota", "Honda"])
        return random.choice(makes)
    
    def _get_mock_car_model(self, car_type):
        """Get a mock car model based on car type"""
        models_by_type = {
            "economy": ["Yaris", "Fit", "Versa", "Rio"],
            "compact": ["Corolla", "Civic", "Mazda3", "Focus"],
            "midsize": ["Camry", "Accord", "Sonata", "Jetta"],
            "standard": ["Camry", "Accord", "Altima", "Passat"],
            "fullsize": ["Avalon", "Taurus", "Impala", "Maxima"],
            "premium": ["3 Series", "A4", "C-Class", "ES"],
            "suv": ["RAV4", "CR-V", "Escape", "Cherokee", "Equinox"],
            "minivan": ["Sienna", "Odyssey", "Pacifica", "Carnival"]
        }
        
        models = models_by_type.get(car_type, ["Model X"])
        return random.choice(models)
    
    def _get_mock_car_features(self, car_type):
        """Get mock features for a car type"""
        base_features = ["Air conditioning", "Power steering", "AM/FM radio"]
        
        features_by_type = {
            "economy": ["Bluetooth"],
            "compact": ["Bluetooth", "USB port"],
            "midsize": ["Bluetooth", "USB port", "Cruise control"],
            "standard": ["Bluetooth", "USB port", "Cruise control", "Keyless entry"],
            "fullsize": ["Bluetooth", "USB port", "Cruise control", "Keyless entry", "Backup camera"],
            "premium": ["Bluetooth", "USB port", "Cruise control", "Keyless entry", "Backup camera", 
                       "Navigation", "Leather seats", "Sunroof"],
            "suv": ["Bluetooth", "USB port", "Cruise control", "Keyless entry", "Backup camera", "4WD"],
            "minivan": ["Bluetooth", "USB port", "Cruise control", "Keyless entry", "Backup camera", 
                       "Power sliding doors", "Third row seating"]
        }
        
        additional_features = features_by_type.get(car_type, [])
        return base_features + additional_features
    
    def get_rental_details(self, rental_id):
        """Get details for a specific car rental"""
        # Check cache first
        cache_key = f"rental_detail_{rental_id}"
        if cache_key in self.cache:
            cached_data = self.cache[cache_key]
            return cached_data["data"]
        
        # If using a mock service or no API key, return mock data
        if not self.api_key or rental_id.startswith(("economy_", "compact_")):
            return self._get_mock_rental_details(rental_id)
        
        # Make API call to car rental service
        try:
            url = f"{self.base_url}/rentals/{rental_id}"
            params = {"api_key": self.api_key}
            
            response = requests.get(url, params=params)
            response.raise_for_status()
            result = response.json()
            
            # Cache the result
            self.cache[cache_key] = {
                "data": result,
                "timestamp": datetime.now().timestamp()
            }
            self._save_cache()
            
            return result
            
        except Exception as e:
            print(f"Error fetching rental details: {e}")
            return self._get_mock_rental_details(rental_id)
    
def _get_mock_rental_details(self, rental_id):
    """Generate mock rental details for a specific rental ID"""
    # Parse info from the rental ID
    parts = rental_id.split('_')
    if len(parts) >= 3:
        car_type = parts[0]
        location_hash = int(parts[1]) if parts[1].isdigit() else 0
        car_index = int(parts[2]) if parts[2].isdigit() else 0
    else:
        car_type = "standard"
        location_hash = 0
        car_index = 0
    
    # Generate consistent mock data based on the rental ID
    make = self._get_mock_car_make(car_type)
    model = self._get_mock_car_model(car_type)
    features = self._get_mock_car_features(car_type)
    
    # Generate a plausible location based on the hash
    locations = ["Paris", "London", "New York", "Tokyo", "Rome", "Barcelona"]
    location = locations[location_hash % len(locations)]
    
    # Calculate a consistent daily rate
    base_rates = {
        "economy": 25, "compact": 30, "midsize": 35, "standard": 40,
        "fullsize": 45, "premium": 60, "suv": 55, "minivan": 65
    }
    daily_rate = base_rates.get(car_type, 40) * (1 + (location_hash % 30) / 100)
    
    # Mock dates (2 weeks from now, for 3 days)
    today = datetime.now()
    start_date = (today + timedelta(days=14)).strftime("%Y-%m-%d")
    end_date = (today + timedelta(days=17)).strftime("%Y-%m-%d")
    days = 3
    
    return {
        "id": rental_id,
        "status": "confirmed",
        "vehicle": {
            "type": car_type,
            "make": make,
            "model": model,
            "year": 2020 + (location_hash % 5),
            "features": features
        },
        "pricing": {
            "daily_rate": round(daily_rate, 2),
            "total_price": round(daily_rate * days, 2),
            "deposit": round(daily_rate * 1.5, 2),
            "taxes_and_fees": round(daily_rate * days * 0.2, 2)
        },
        "location": {
            "pickup": {
                "address": f"{location} Airport Car Rental",
                "date": start_date,
                "time": "10:00"
            },
            "dropoff": {
                "address": f"{location} Airport Car Rental",
                "date": end_date,
                "time": "10:00"
            }
        },
        "customer_info": {
            "booking_reference": f"BR-{100000 + location_hash}-{car_index}",
            "insurance": "basic"
        },
        "cancellation_policy": "Free cancellation up to 24 hours before pickup"
    }

def book_car_rental(self, car_id, user_info):
    """Book a specific car rental"""
    # In a real app, this would create an actual booking
    # For our mock implementation, we'll just return details with a confirmed status
    
    rental_details = self.get_rental_details(car_id)
    
    # Update with user info
    if user_info:
        rental_details["customer_info"].update({
            "name": user_info.get("name", "Guest User"),
            "email": user_info.get("email", "guest@example.com"),
            "phone": user_info.get("phone", "")
        })
    
    # Generate a booking reference
    rental_details["customer_info"]["booking_reference"] = f"BR-{random.randint(100000, 999999)}"
    rental_details["status"] = "confirmed"
    
    return rental_details

def cancel_booking(self, booking_reference):
    """Cancel a car rental booking"""
    # In a real app, this would cancel an actual booking
    # For our mock implementation, we'll just return a cancellation confirmation
    
    return {
        "status": "cancelled",
        "booking_reference": booking_reference,
        "cancellation_fee": 0,
        "message": "Your booking has been successfully cancelled.",
        "refund_status": "processing",
        "timestamp": datetime.now().timestamp()
    }