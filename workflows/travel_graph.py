from agents.chat_agent import ChatAgent
from agents.information_agent import InformationAgent
from agents.recommend_agent import RecommendAgent
from agents.strategy_agent import StrategyAgent
from agents.route_agent import RouteAgent
from agents.communication_agent import CommunicationAgent

# This is a simplified state graph manager since we're not using the actual langgraph library
class TravelGraph:
    def __init__(self):
        """Initialize the travel planning workflow graph"""
        self.chat_agent = ChatAgent()
        self.info_agent = InformationAgent()
        self.recommend_agent = RecommendAgent()
        self.strategy_agent = StrategyAgent()
        self.route_agent = RouteAgent()
        self.comm_agent = CommunicationAgent()
        
        # Store state
        self.state = {
            "user_info": {},
            "attractions": [],
            "selected_attractions": [],
            "additional_attractions": [],
            "should_rent_car": False,
            "rental_post": None,
            "itinerary": [],
            "budget": {}
        }
    
    def process_step(self, step_name, **kwargs):
        """Process a specific step in the workflow"""
        if step_name == "chat":
            return self._process_chat(**kwargs)
        elif step_name == "information":
            return self._process_information(**kwargs)
        elif step_name == "recommend":
            return self._process_recommend(**kwargs)
        elif step_name == "strategy":
            return self._process_strategy(**kwargs)
        elif step_name == "route":
            return self._process_route(**kwargs)
        elif step_name == "communication":
            return self._process_communication(**kwargs)
        else:
            return {"error": f"Unknown step: {step_name}"}
    
    def _process_chat(self, user_input=None, **kwargs):
        """Process chat agent step"""
        """Process user chat, collect info incrementally, and advance when complete."""
        # Collect and merge info
        result = self.chat_agent.collect_info(user_input or "", self.state["user_info"])
        
        # Update state with new information
        if result.get("state"):
            # Merge new state with existing state instead of overwriting
            self.state["user_info"].update(result["state"])
            print(f"[DEBUG] Updated user info in _process_chat: {self.state['user_info']}")  # Debug log
        
        # Base response structure
        base = {
            "state": self.state,
            "response": result["response"],
            "missing_fields": result.get("missing_fields", [])
        }
        
        if not result["complete"]:
            base["next_step"] = "chat"
            return base
            
        # If complete, chain to information step automatically
        info = self._process_information()
        info.update({
            "previous_response": result["response"],
            "state": self.state
        })
        return info
    
    def _process_information(self, **kwargs):
        """Process information agent step"""
        city = self.state["user_info"].get("city")
        city_coordinates = self.info_agent.city2geocode(city)
        if not city_coordinates:
            return {
                "next_step": "chat",
                "response": "We need to know which city you want to visit."
            }
        
        # Get attractions for the specified city
        attractions = self.info_agent.get_attractions(city_coordinates["lat"], city_coordinates["lng"], poi_type="tourist_attraction", sort_by="rating")
        self.state["attractions"] = attractions
        
        return {
            "next_step": "recommend",
            "response": f"Found {len(attractions)} attractions in {city}.",
            "attractions": attractions,
            "map_data": self.recommend_agent.generate_map_data(attractions),
            "state": self.state
        }
    
    def _process_recommend(self, selected_attraction_ids=None, **kwargs):
        """Process recommend agent step"""
        user_prefs = self.state["user_info"]
        attractions = self.state["attractions"]
        
        if selected_attraction_ids:
            # User has selected specific attractions
            selected_attractions = [
                a for a in attractions 
                if a["id"] in selected_attraction_ids
            ]
            self.state["selected_attractions"] = selected_attractions
            
            return {
                "next_step": "strategy",
                "response": f"You've selected {len(selected_attractions)} attractions.",
                "selected_attractions": selected_attractions
            }
        else:
            # Recommend attractions to the user
            recommended = self.recommend_agent.recommend_core_attractions(user_prefs, attractions)
            
            return {
                "next_step": "recommend",  # Stay on this step until user selects attractions
                "response": "Here are some recommended attractions for you.",
                "recommended_attractions": recommended,
                "map_data": self.recommend_agent.generate_map_data(recommended)
            }
    
    def _process_strategy(self, **kwargs):
        """Process strategy agent step"""
        selected_attractions = self.state["selected_attractions"]
        total_days = self.state["user_info"].get("days", 1)
        
        print(f"[DEBUG] User info in _process_strategy before get_ai_recommendation: {self.state['user_info']}")  # Debug log
        
        # Plan remaining time and suggest additional attractions
        strategy_result = self.strategy_agent.plan_remaining_time(
            selected_attractions, 
            total_days,
            self.state["attractions"]
        )
        
        self.state["additional_attractions"] = strategy_result["additional_attractions"]
        
        # Check if car rental is recommended
        should_rent_car = self.strategy_agent.should_rent_car(
            selected_attractions, 
            self.state["user_info"].get("city", ""),
            self.state["user_info"]
        )
        
        self.state["should_rent_car"] = should_rent_car
        
        # Get AI recommendation about the overall plan
        ai_recommendation = self.strategy_agent.get_ai_recommendation(
            self.state["user_info"],
            selected_attractions,
            total_days
        )
        
        next_step = "communication" if should_rent_car else "route"
        
        return {
            "next_step": next_step,
            "response": ai_recommendation,
            "remaining_hours": strategy_result["remaining_hours"],
            "additional_attractions": strategy_result["additional_attractions"],
            "should_rent_car": should_rent_car
        }
    
    def _process_communication(self, response_message=None, **kwargs):
        """Process communication agent step"""
        if response_message and self.state["rental_post"]:
            # Handle response to rental post
            reply = self.comm_agent.handle_rental_response(
                self.state["rental_post"],
                response_message
            )
            
            return {
                "next_step": "route",  # Move to route planning after rental communication
                "response": "Thank you for handling the car rental.",
                "reply": reply
            }
        else:
            # Generate rental post
            location = self.state["user_info"].get("city", "")
            duration = self.state["user_info"].get("days", 1)
            
            rental_post = self.comm_agent.post_car_rental_request(
                location,
                duration,
                self.state["user_info"]
            )
            
            self.state["rental_post"] = rental_post
            
            return {
                "next_step": "route",  # Continue with route planning while waiting for responses
                "response": "I've created a car rental request post for you.",
                "rental_post": rental_post
            }
    
    def _process_route(self, start_date=None, **kwargs):
        """Process route agent step"""
        if not start_date:
            start_date = kwargs.get("start_date", "2025-03-20")  # Default start date
        
        # Get all attractions (selected + additional)
        all_attractions = self.state["selected_attractions"] + self.state["additional_attractions"]
        
        # Calculate optimal route
        optimal_route = self.route_agent.get_optimal_route(all_attractions)
        
        # Generate itinerary
        days = self.state["user_info"].get("days", 1)
        itinerary = self.route_agent.generate_itinerary(optimal_route, start_date, days)
        
        # Estimate budget
        budget = self.route_agent.estimate_budget(
            all_attractions,
            self.state["user_info"]
        )
        
        # Store in state
        self.state["itinerary"] = itinerary
        self.state["budget"] = budget
        
        # Generate confirmation message
        confirmation = self.comm_agent.generate_booking_confirmation(
            itinerary,
            budget,
            self.state["should_rent_car"]
        )
        
        return {
            "next_step": "complete",
            "response": confirmation,
            "itinerary": itinerary,
            "budget": budget,
            "optimal_route": optimal_route
        }
    
    def get_current_state(self):
        """Get the current state of the workflow"""
        return self.state