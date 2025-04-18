import os
import requests
import json
from datetime import datetime, timedelta

class CarRentalService:
    def __init__(self, api_key=None):
        """Initialize the car rental service with API key"""
        self.api_key = api_key or os.environ.get("CAR_RENTAL_API_KEY")
        self.base_url = "https://partners.api.skyscanner.net/apiservices/v1/carhire/live"
        self.cache_file = "data/car_rental_cache.json"
        self.cache = self._load_cache()
        self.session_tokens = {}
    
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
    
    def search_available_cars(self, location, start_date, end_date, vehicle_type=None, driver_age=30, user_ip=None, drop_off_location=None):
        """Search for available cars at a location and date range"""
        # Check cache first
        cache_key = self._cache_key(location, start_date, end_date, vehicle_type)
        if cache_key in self.cache:
            cached_data = self.cache[cache_key]
            # Check if cache is still valid (less than 1 hour old)
            if datetime.now().timestamp() - cached_data["timestamp"] < 3600:
                return cached_data["data"]
        
        # Make API call to car rental service
        try:
            # Create search request
            create_url = f"{self.base_url}/search/create"
            
            # Prepare request payload
            payload = {
                "market": "US",  # Default market
                "locale": "en-US",
                "currency": "USD",
                "pickUpDate": start_date,
                "dropOffDate": end_date,
                "pickUpLocation": location,
                "driverAge": driver_age
            }
            
            # Add optional parameters if provided
            if drop_off_location:
                payload["dropOffLocation"] = drop_off_location
            
            if user_ip:
                payload["userIp"] = user_ip
                
            # Add vehicle type as included agent if specified
            if vehicle_type:
                payload["includedAgentIds"] = [vehicle_type]
            
            headers = {
                "Content-Type": "application/json",
                "api-key": self.api_key
            }
            
            # Make the create request
            create_response = requests.post(create_url, json=payload, headers=headers)
            create_response.raise_for_status()
            create_result = create_response.json()
            
            # Get session token for polling
            session_token = create_result.get("sessionToken")
            if not session_token:
                raise Exception("No session token received from API")
            
            # Store session token with timestamp
            self.session_tokens[cache_key] = {
                "token": session_token,
                "timestamp": datetime.now().timestamp()
            }
            
            # Poll for results
            poll_url = f"{self.base_url}/search/poll/{session_token}"
            
            # Poll until status is completed or timeout
            max_attempts = 5
            attempts = 0
            poll_result = None
            
            while attempts < max_attempts:
                poll_response = requests.post(poll_url, headers=headers)
                poll_response.raise_for_status()
                poll_result = poll_response.json()
                
                if poll_result.get("status") == "completed":
                    break
                
                # Wait before polling again
                attempts += 1
                if attempts < max_attempts:
                    import time
                    time.sleep(2)
            
            # Process the results into our standard format
            if poll_result:
                result = self._process_api_results(poll_result, location, start_date, end_date)
            else:
                raise Exception("Polling failed to complete")
            
            # Cache the result
            self.cache[cache_key] = {
                "data": result,
                "timestamp": datetime.now().timestamp()
            }
            self._save_cache()
            
            return result
            
        except Exception as e:
            print(f"Error fetching car rental data: {e}")
            raise
    
    def _process_api_results(self, api_result, location, start_date, end_date):
        """Process API results into our standard format"""
        available_cars = []
        
        quotes = api_result.get("quotes", [])
        agents = api_result.get("agents", {})
        vendors = api_result.get("vendors", {})
        
        for quote in quotes:
            vendor_id = quote.get("vendorId")
            agent_id = quote.get("agentId")
            
            vendor_info = vendors.get(vendor_id, {})
            agent_info = agents.get(agent_id, {})
            
            car_type = quote.get("carGroupInfo", {}).get("category", "standard").lower()
            
            car = {
                "id": quote.get("quoteId", ""),
                "vehicle_type": car_type,
                "make": vendor_info.get("name", "Unknown"),
                "model": quote.get("carGroupInfo", {}).get("name", "Unknown Model"),
                "year": datetime.now().year,  # API doesn't provide year
                "daily_rate": quote.get("price", {}).get("amount", 0) / max(1, (datetime.strptime(end_date, "%Y-%m-%d") - datetime.strptime(start_date, "%Y-%m-%d")).days),
                "total_price": quote.get("price", {}).get("amount", 0),
                "location": {
                    "pickup": location,
                    "dropoff": quote.get("dropOffLocation", location)
                },
                "dates": {
                    "pickup": start_date,
                    "dropoff": end_date
                },
                "features": quote.get("carGroupInfo", {}).get("features", []),
                "availability": "available",
                "deep_link": quote.get("deepLink", ""),
                "vendor": vendor_info.get("name", ""),
                "agent": agent_info.get("name", "")
            }
            
            available_cars.append(car)
        
        return {
            "location": location,
            "search_dates": {
                "start": start_date,
                "end": end_date
            },
            "available_cars": available_cars,
            "source": "api"
        }
    
    def get_rental_details(self, rental_id):
        """Get details for a specific car rental"""
        # Check cache first
        cache_key = f"rental_detail_{rental_id}"
        if cache_key in self.cache:
            cached_data = self.cache[cache_key]
            return cached_data["data"]
        
        # Make API call to car rental service
        try:
            url = f"{self.base_url}/rentals/{rental_id}"
            headers = {"api-key": self.api_key}
            
            response = requests.get(url, headers=headers)
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
            raise
    
    def book_car_rental(self, car_id, user_info):
        """Book a specific car rental"""
        try:
            url = f"{self.base_url}/bookings/create"
            headers = {
                "Content-Type": "application/json",
                "api-key": self.api_key
            }
            
            payload = {
                "quoteId": car_id,
                "customerDetails": {
                    "name": user_info.get("name"),
                    "email": user_info.get("email"),
                    "phone": user_info.get("phone")
                }
            }
            
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            print(f"Error booking car rental: {e}")
            raise
    
    def cancel_booking(self, booking_reference):
        """Cancel a car rental booking"""
        try:
            url = f"{self.base_url}/bookings/{booking_reference}/cancel"
            headers = {"api-key": self.api_key}
            
            response = requests.post(url, headers=headers)
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            print(f"Error cancelling booking: {e}")
            raise


# Test code to demonstrate the CarRentalService functionality
if __name__ == "__main__":
    # Create an instance of the CarRentalService
    car_service = CarRentalService()
    
    # Set up test parameters
    location = "Los Angeles"
    today = datetime.now()
    start_date = (today + timedelta(days=7)).strftime("%Y-%m-%d")
    end_date = (today + timedelta(days=10)).strftime("%Y-%m-%d")
    
    print(f"Searching for cars in {location} from {start_date} to {end_date}...")
    
    try:
        # Search for available cars
        search_result = car_service.search_available_cars(location, start_date, end_date)
        
        # Print search results summary
        print(f"\nFound {len(search_result['available_cars'])} available cars in {location}")
        
        # Print details of the first car
        if search_result['available_cars']:
            first_car = search_result['available_cars'][0]
            print("\nFirst available car details:")
            print(f"Make/Model: {first_car['make']} {first_car['model']}")
            print(f"Type: {first_car['vehicle_type']}")
            print(f"Daily rate: ${first_car['daily_rate']:.2f}")
            print(f"Total price: ${first_car['total_price']:.2f}")
            
            # Get rental details for the first car
            car_id = first_car['id']
            print(f"\nGetting detailed information for car ID: {car_id}")
            rental_details = car_service.get_rental_details(car_id)
            
            # Book the car
            print("\nBooking the car...")
            user_info = {
                "name": "John Doe",
                "email": "john.doe@example.com",
                "phone": "123-456-7890"
            }
            booking_result = car_service.book_car_rental(car_id, user_info)
            
            # Print booking confirmation
            print(f"\nBooking confirmed!")
            print(f"Booking reference: {booking_result.get('bookingReference')}")
            print(f"Status: {booking_result.get('status')}")
            
            # Cancel the booking
            booking_ref = booking_result.get('bookingReference')
            print(f"\nCancelling booking {booking_ref}...")
            cancellation_result = car_service.cancel_booking(booking_ref)
            
            # Print cancellation confirmation
            print(f"Cancellation status: {cancellation_result.get('status')}")
            print(f"Message: {cancellation_result.get('message', 'Booking successfully cancelled')}")
        else:
            print("No cars available for the selected dates and location.")
    except Exception as e:
        print(f"An error occurred during testing: {e}")