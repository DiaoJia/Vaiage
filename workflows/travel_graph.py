from agents.chat_agent import ChatAgent
from agents.information_agent import InformationAgent
from agents.recommend_agent import RecommendAgent
from agents.strategy_agent import StrategyAgent
from agents.route_agent import RouteAgent
from agents.communication_agent import CommunicationAgent
from datetime import datetime
from langchain.schema import AIMessage

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
            "budget": {},
            "ai_recommendation_generated": False,
            "user_input_processed": False
        }
        
        # Store session state
        self.session_states = {}
    
    def get_session_state(self, session_id):
        """Get or create session state"""
        if session_id not in self.session_states:
            self.session_states[session_id] = self.state.copy()
        return self.session_states[session_id]
    
    def process_step(self, step_name, session_id=None, **kwargs):
        """Process a specific step in the workflow"""
        print(f"[DEBUG] Processing step {step_name} with session_id: {session_id}")
        print(f"[DEBUG] Initial kwargs: {kwargs}")
        
        # Get session state
        if session_id:
            self.state = self.get_session_state(session_id)
            print(f"[DEBUG] Retrieved session state: {self.state}")
        else:
            # If no session_id, create a new one
            session_id = str(id(self))
            self.state = self.get_session_state(session_id)
            print(f"[DEBUG] Created new session with id: {session_id}")
        
        # Update state flags from kwargs if provided
        if 'ai_recommendation_generated' in kwargs:
            self.state['ai_recommendation_generated'] = kwargs['ai_recommendation_generated'].lower() == 'true'
            print(f"[DEBUG] Updated ai_recommendation_generated to: {self.state['ai_recommendation_generated']}")
        if 'user_input_processed' in kwargs:
            self.state['user_input_processed'] = kwargs['user_input_processed'].lower() == 'true'
            print(f"[DEBUG] Updated user_input_processed to: {self.state['user_input_processed']}")
        
        print(f"[DEBUG] Current state before processing: {self.state}")
        
        if step_name == "chat":
            result = self._process_chat(**kwargs)
        elif step_name == "information":
            result = self._process_information(**kwargs)
        elif step_name == "recommend":
            result = self._process_recommend(**kwargs)
        elif step_name == "strategy":
            result = self._process_strategy(**kwargs)
        elif step_name == "route":
            result = self._process_route(**kwargs)
        elif step_name == "communication":
            result = self._process_communication(**kwargs)
        else:
            result = {"error": f"Unknown step: {step_name}"}
        
        # Always save state and include session_id in result
        self.session_states[session_id] = self.state.copy()
        result["session_id"] = session_id
        print(f"[DEBUG] Saved session state: {self.session_states[session_id]}")
        
        print(f"[DEBUG] Final state after processing: {self.state}")
        print(f"[DEBUG] Returning result: {result}")
        return result
    
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
            "stream": result.get("stream"),
            "missing_fields": result.get("missing_fields", [])
        }
        
        if not result["complete"]:
            base["next_step"] = "chat"
            return base
            
        # If complete, chain to information step automatically
        info = self._process_information()
        info.update({
            "state": self.state
        })
        return info
    
    def _process_information(self, **kwargs):
        """Process information agent step"""
        city = self.state["user_info"].get("city")
        city_coordinates = self.info_agent.city2geocode(city)
        if not city_coordinates:
            # Create a generator that yields the error message
            def error_generator():
                yield AIMessage(content="We need to know which city you want to visit.")
            
            return {
                "next_step": "chat",
                "stream": error_generator()
            }
        
        # Get attractions for the specified city
        attractions = self.info_agent.get_attractions(city_coordinates["lat"], city_coordinates["lng"], poi_type="tourist_attraction", sort_by="rating")
        self.state["attractions"] = attractions
        
        # Create a generator that yields the information message
        def info_generator():
            yield AIMessage(content=f"Found {len(attractions)} attractions in {city}.")
        
        return {
            "next_step": "recommend",
            "stream": info_generator(),
            "attractions": attractions,
            "map_data": self.recommend_agent.generate_map_data(attractions),
            "state": self.state
        }
    
    def _process_recommend(self, selected_attraction_ids=None, **kwargs):
        """Process recommend agent step"""
        try:
            user_prefs = self.state["user_info"]
            attractions = self.state["attractions"]
            
            # Check if we have selected_attraction_ids in kwargs
            if 'selected_attraction_ids' in kwargs and kwargs['selected_attraction_ids']:
                selected_attraction_ids = kwargs['selected_attraction_ids']
            
            if selected_attraction_ids:
                # User has selected specific attractions
                selected_attractions = [
                    a for a in attractions 
                    if a and a.get("id") and a["id"] in selected_attraction_ids
                ]
                self.state["selected_attractions"] = selected_attractions
                
                # Create a generator that yields a transition message
                def transition_generator():
                    yield AIMessage(content="Processing your selected attractions...")
                
                return {
                    "next_step": "strategy",
                    "stream": transition_generator(),
                    "selected_attractions": selected_attractions
                }
            else:
                # Recommend attractions to the user
                if not attractions:
                    return {
                        "next_step": "recommend",
                        "stream": None,
                        "response": "No attractions available for recommendation.",
                        "recommended_attractions": [],
                        "map_data": []
                    }
                
                recommended = self.recommend_agent.recommend_core_attractions(user_prefs, attractions)
                
                # Create a generator that yields the recommendation message
                def recommendation_generator():
                    yield AIMessage(content="Here are some recommended attractions for you.")
                
                return {
                    "next_step": "recommend",  # Stay on this step until user selects attractions
                    "stream": recommendation_generator(),
                    "recommended_attractions": recommended,
                    "map_data": self.recommend_agent.generate_map_data(recommended)
                }
        except Exception as e:
            print(f"Error in _process_recommend: {str(e)}")
            return {
                "next_step": "error",
                "stream": None,
                "response": "An error occurred while processing recommendations.",
                "error": str(e)
            }
    
    def _process_strategy(self, **kwargs):
        """Process strategy agent step"""
        print(f"[DEBUG] Entering _process_strategy with kwargs: {kwargs}")
        print(f"[DEBUG] Current state before processing: {self.state}")
        
        # Check if this is a confirm selection request
        is_confirm_selection = kwargs.get('user_input', '').lower() == 'here are my selected attractions'
        print(f"[DEBUG] Is confirm selection: {is_confirm_selection}")
        print(f"[DEBUG] Current ai_recommendation_generated: {self.state['ai_recommendation_generated']}")
        
        # If recommendations haven't been generated yet and this is a confirm selection request
        if not self.state['ai_recommendation_generated'] and is_confirm_selection:
            print("[DEBUG] Generating recommendations for the first time (confirm selection)")
            
            # Update state flags BEFORE generating recommendations
            self.state['ai_recommendation_generated'] = True
            self.state['user_input_processed'] = True
            print("[DEBUG] Set ai_recommendation_generated and user_input_processed to True")
            
            selected_attractions = self.state["selected_attractions"]
            total_days = self.state["user_info"].get("days", 1)
            
            print(f"[DEBUG] User info in _process_strategy before get_ai_recommendation: {self.state['user_info']}")
            
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
            print(f"[DEBUG] Next step will be: {next_step}")
            
            # Create a copy of the state to return
            state_copy = self.state.copy()
            print(f"[DEBUG] State to be returned: {state_copy}")
            
            return {
                "next_step": next_step,
                "stream": ai_recommendation,
                "remaining_hours": strategy_result["remaining_hours"],
                "additional_attractions": strategy_result["additional_attractions"],
                "should_rent_car": should_rent_car,
                "state": state_copy,
                "ai_recommendation_generated": True,
                "user_input_processed": True
            }
        elif self.state['ai_recommendation_generated']:
            print("[DEBUG] Recommendations already generated, moving to next step")
            next_step = "communication" if self.state.get("should_rent_car", False) else "route"
            print(f"[DEBUG] Moving to next step: {next_step}")
            
            # Create a generator that yields the transition message
            def transition_generator():
                yield AIMessage(content="Moving to the next step...")
            
            # Create a copy of the state to return
            state_copy = self.state.copy()
            print(f"[DEBUG] State to be returned: {state_copy}")
            
            return {
                "next_step": next_step,
                "stream": transition_generator(),
                "state": state_copy,
                "ai_recommendation_generated": True,
                "user_input_processed": True
            }
        else:
            print("[DEBUG] Not a confirm selection request and recommendations not generated yet")
            # Create a generator that yields a message asking for confirmation
            def confirmation_generator():
                yield AIMessage(content="Please click the 'Confirm Selection' button to proceed with your travel plan.")
            
            # Create a copy of the state to return
            state_copy = self.state.copy()
            print(f"[DEBUG] State to be returned: {state_copy}")
            
            return {
                "next_step": "strategy",
                "stream": confirmation_generator(),
                "state": state_copy,
                "ai_recommendation_generated": False,
                "user_input_processed": False
            }
    
    def _process_communication(self, response_message=None, **kwargs):
        """Process communication agent step"""
        if response_message and self.state["rental_post"]:
            # Handle response to rental post
            reply = self.comm_agent.handle_rental_response(
                self.state["rental_post"],
                response_message
            )
            
            # Create a generator that yields the response message
            def reply_generator():
                yield AIMessage(content="Thank you for handling the car rental.")
            
            return {
                "next_step": "route",  # Move to route planning after rental communication
                "stream": reply_generator(),
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
            
            # Create a generator that yields the response message
            def response_generator():
                yield AIMessage(content="I've created a car rental request post for you.")
            
            return {
                "next_step": "route",  # Continue with route planning while waiting for responses
                "stream": response_generator(),
                "rental_post": rental_post
            }
    
    def _process_route(self, start_date=None, **kwargs):
        """Process route agent step"""
        try:
            if not start_date:
                start_date = kwargs.get("start_date", datetime.now().strftime("%Y-%m-%d"))  # Default to today's date
            
            # Get all attractions (selected + additional)
            all_attractions = self.state["selected_attractions"] + self.state["additional_attractions"]
            
            if not all_attractions:
                return {
                    "next_step": "complete",
                    "response": "No attractions selected for the trip.",
                    "itinerary": [],
                    "budget": {},
                    "optimal_route": []
                }
            
            # Calculate optimal route
            optimal_route = self.route_agent.get_optimal_route(all_attractions)
            
            # Generate itinerary
            days = int(self.state["user_info"].get("days", 1))  # Ensure days is an integer
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
            
        except Exception as e:
            # Log the error for debugging
            print(f"Error in process route: {str(e)}")
            return {
                "next_step": "error",
                "response": "An error occurred while planning your route. Please try again.",
                "error": str(e)
            }
    
    def get_current_state(self):
        """Get the current state of the workflow"""
        return self.state