from agents.chat_agent import ChatAgent
from agents.information_agent import InformationAgent
from agents.recommend_agent import RecommendAgent
from agents.strategy_agent import StrategyAgent
from agents.route_agent import RouteAgent
from agents.communication_agent import CommunicationAgent
from datetime import datetime, timedelta
from langchain.schema import AIMessage
from workflows.evaluation import evaluate_state_with_llm

import traceback
# This is a simplified state graph manager since we're not using the actual langgraph library
class TravelGraph:
    def __init__(self):
        self.chat_agent = ChatAgent()
        self.info_agent = InformationAgent() # InfoAgent now handles LLM re-ranking
        self.recommend_agent = RecommendAgent() # Still used for map_data, etc.
        self.strategy_agent = StrategyAgent()
        self.route_agent = RouteAgent()
        self.comm_agent = CommunicationAgent()
        
        self.state = { # Default state for a new session
            "user_info": {},
            "attractions": [], # This will hold LLM-ranked attractions from InfoAgent
            "weather_summary": None, # To store weather summary string
            "selected_attractions": [],
            "additional_attractions": [],
            "should_rent_car": False,
            "rental_post": None,
            "itinerary": [],
            "budget": {},
            "ai_recommendation_generated": False, # Flag for strategy AI advice
        }
        self.session_states = {} # To store states for different sessions
    
    def get_session_state(self, session_id):
        if session_id not in self.session_states:
            # Create a new state by copying the default state structure
            self.session_states[session_id] = {
                "user_info": {}, "attractions": [], "weather_summary": None,
                "selected_attractions": [], "additional_attractions": [],
                "should_rent_car": False, "rental_post": None, "itinerary": [], "budget": {},
                "ai_recommendation_generated": False,
            }
        return self.session_states[session_id]
    
    def process_step(self, step_name, session_id=None, **kwargs):
        # print(f"[DEBUG] Processing step {step_name} for session_id: {session_id}")
        # print(f"[DEBUG] Initial kwargs: {kwargs}")
        
        if session_id:
            self.state = self.get_session_state(session_id)
            # print(f"[DEBUG] Retrieved session state: {self.state}")
        else:
            session_id = str(id(self)) # Fallback if no session_id, though it should be provided
            self.state = self.get_session_state(session_id)
            print(f"[WARN] No session_id provided, created fallback session: {session_id}")
        
        if 'ai_recommendation_generated' in kwargs: # Ensure flag is a boolean
            self.state['ai_recommendation_generated'] = str(kwargs['ai_recommendation_generated']).lower() == 'true'
        
        # print(f"[DEBUG] State before processing {step_name}: {self.state}")
        
        result = {}
        if step_name == "chat":
            result = self._process_chat(**kwargs)
        elif step_name == "information":
            result = self._process_information(**kwargs) # This will now call the updated InfoAgent
        elif step_name == "recommend":
            result = self._process_recommend(**kwargs) # This uses the already LLM-ranked list
        elif step_name == "strategy":
            result = self._process_strategy(**kwargs)
        elif step_name == "route":
            result = self._process_route(**kwargs)
        elif step_name == "communication":
            result = self._process_communication(**kwargs)
        else:
            result = {"error": f"Unknown step: {step_name}"}
        
        self.session_states[session_id] = self.state.copy() # Save a copy of the modified state
        result["session_id"] = session_id # Ensure session_id is always in the result
        # print(f"[DEBUG] State after processing {step_name}: {self.state}")
        # print(f"[DEBUG] Result for {step_name}: {result}")
        return result
    
    def _process_chat(self, user_input=None, **kwargs):
        current_user_info = self.state.get("user_info", {}).copy() # Important to work with a copy for updates
        chat_result = self.chat_agent.collect_info(user_input or "", current_user_info)
        
        if chat_result.get("state"):
            self.state["user_info"].update(chat_result["state"]) # Merge updates
            # print(f"[DEBUG] Updated user_info in _process_chat: {self.state['user_info']}")

        response_data = {
            "state": self.state.copy(), # Return a fresh copy of the current state
            "stream": chat_result.get("stream"),
            "missing_fields": chat_result.get("missing_fields", [])
        }
        
        if not chat_result.get("complete", False): 
            response_data["next_step"] = "chat"
            return response_data
            
        # If chat is complete, automatically proceed to information gathering
        # The state (self.state) is already updated, _process_information will use it.
        info_step_result = self._process_information() 
        return info_step_result # This result will contain next_step, stream, data, and state
    
    def _process_information(self, **kwargs):
        user_prefs = self.state["user_info"]
        city = user_prefs.get("city")

        if not city:
            def error_gen(): yield AIMessage(content="Please tell me which city you'd like to visit.")
            return {"next_step": "chat", "stream": error_gen(), "missing_fields": ["city"], "state": self.state.copy()}

        city_coordinates = self.info_agent.city2geocode(city)
        if not city_coordinates:
            def error_gen(): yield AIMessage(content=f"Sorry, I couldn't find coordinates for {city}.")
            return {"next_step": "chat", "stream": error_gen(), "state": self.state.copy()}
        
        # Get weather summary first
        weather_summary_str = None
        user_start_date = user_prefs.get("start_date", "not decided")
        user_days_str = user_prefs.get("days")

        # Handle "not decided" case by setting start date to 7 days from now
        if user_start_date == "not decided":
            user_start_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
            user_prefs["start_date"] = user_start_date  # Update the state with the new start date

        if user_days_str:
            try:
                num_days = int(user_days_str)
                weather_data_result = self.info_agent.get_weather(
                    city_coordinates["lat"], city_coordinates["lng"],
                    user_start_date, num_days, summary=True
                )
                if weather_data_result and 'summary' in weather_data_result:
                    summary_val = weather_data_result['summary']
                    if hasattr(summary_val, 'content'): # If AIMessage
                        weather_summary_str = summary_val.content
                    elif isinstance(summary_val, str):
                        weather_summary_str = summary_val
                    self.state["weather_summary"] = weather_summary_str
                    print(f"[DEBUG] Weather summary set in state: '{weather_summary_str}'")
                else:
                    print(f"[DEBUG] Weather summary not found or in unexpected format: {weather_data_result}")
            except ValueError:
                print(f"[ERROR] Invalid 'days' for weather: {user_days_str}")
            except Exception as e:
                print(f"[ERROR] Exception fetching weather summary: {e}")
                traceback.print_exc()
        else:
            print("[DEBUG] Weather info not fetched (no days).")
            
        # Get attractions - InfoAgent now handles LLM re-ranking internally
        print(f"[DEBUG] Calling info_agent.get_attractions for '{city}' with user_prefs and weather.")
        attractions_from_info_agent = self.info_agent.get_attractions(
            lat=city_coordinates["lat"],
            lng=city_coordinates["lng"],
            user_prefs=user_prefs, # Pass full user_prefs
            weather_summary=self.state.get("weather_summary"), # Pass fetched weather summary
            number=15, # Desired number of top attractions after LLM ranking
            poi_type="tourist_attraction"
            # sort_by="rating" # Initial sort inside get_attractions before LLM
        )
        
        self.state["attractions"] = attractions_from_info_agent if attractions_from_info_agent else []
        print(f"[DEBUG] attractions state updated with {len(self.state['attractions'])} LLM-ranked items.")
        
        def info_gen_message():
            if self.state["attractions"]:
                yield AIMessage(content=f"I've prepared a personalized list of {len(self.state['attractions'])} attractions in {city} for you, considering your preferences and the weather. Please take a look and select your favorites.")
            else:
                yield AIMessage(content=f"I couldn't find attractions in {city} matching your preferences right now. You might want to try different criteria or another city.")
        
        return {
            "next_step": "recommend",
            "stream": info_gen_message(),
            "attractions": self.state["attractions"], # This list is now LLM-ranked
            "map_data": self.recommend_agent.generate_map_data(self.state["attractions"]), # recommend_agent helps with map data
            "state": self.state.copy()
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
                
                recommended = self.recommend_agent.recommend_core_attractions(user_prefs, attractions,)
                
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
        print(f"[DEBUG] In _process_strategy, Is confirm selection: {is_confirm_selection}")
        print(f"[DEBUG] In _process_strategy, Current ai_recommendation_generated: {self.state['ai_recommendation_generated']}")
        
        # If recommendations haven't been generated yet and this is a confirm selection request,first time entering this step
        if not self.state['ai_recommendation_generated'] and is_confirm_selection:
            print("[DEBUG] Generating recommendations for the first time (confirm selection)")
            
            # Update state flags BEFORE generating recommendations
            self.state['ai_recommendation_generated'] = True
            self.state['user_input_processed'] = True
            print("[DEBUG] In _process_strategy, Set ai_recommendation_generated and user_input_processed to True")
            
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
            print(f"[DEBUG] In _process_strategy, Should rent car: {should_rent_car}")
            self.state["should_rent_car"] = should_rent_car
            
            # Get AI recommendation about the overall plan
            ai_recommendation = self.strategy_agent.get_ai_recommendation(
                self.state["user_info"],
                selected_attractions,
                total_days,
                should_rent_car=should_rent_car  # Pass the car rental decision to the AI
            )
            
            # Create a copy of the state to return
            state_copy = self.state.copy()
            print(f"[DEBUG] State to be returned: {state_copy}")
            
            return {
                "next_step": "strategy",
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
            # Only move to communication step if car rental is actually needed
            next_step = "communication" if self.state.get("should_rent_car", False) else "route"
            print(f"[DEBUG] Next step will be: {next_step}")
            
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
        
    # After strategy step + self.state.get("should_rent_car", False) == True
    def _process_communication(self, response_message=None, **kwargs):
        """Process communication agent step"""
        if response_message and self.state["rental_post"]:  ## 这一步是做什么？？
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
                yield AIMessage(content="we recommmend you to rent a car for your trip, I've created a car rental request post for you.Feel free to use it.")
            
            return {
                "next_step": "route",  # Continue with route planning while waiting for responses
                "stream": response_generator(),
                "rental_post": rental_post
            }
    
    def _process_route(self, start_date=None, **kwargs):
        """Process route agent step"""
        try:
            # Get start date from user preferences, fallback to provided start_date, then to current date
            start_date = self.state["user_info"].get("start_date") or start_date or datetime.now().strftime("%Y-%m-%d")
            
            # Get all attractions (selected + additional)
            all_attractions = self.state["selected_attractions"] + self.state["additional_attractions"]
            
            print(f"[DEBUG] All attractions: {all_attractions}")
            
            if not all_attractions:
                return {
                    "next_step": "complete",
                    "response": "No attractions selected for the trip.",
                    "itinerary": [],
                    "budget": {},
                    "optimal_route": []
                }
            
            # Generate itinerary first
            days = int(self.state["user_info"].get("days", 1))  # Ensure days is an integer
            itinerary = self.route_agent.generate_itinerary(all_attractions, start_date, days)
            # Fix: convert start_date to datetime if it's a string
            if isinstance(start_date, str):
                start_date_dt = datetime.strptime(start_date, "%Y-%m-%d")
            else:
                start_date_dt = start_date
            end_date = (start_date_dt + timedelta(days=days)).strftime("%Y-%m-%d")
            # Extract the optimal route from the itinerary
            optimal_route = []
            for day in itinerary:
                optimal_route.extend(day["spots"])
           
            # Estimate budget

            if self.state["should_rent_car"]:
                car_info = self.info_agent.search_car_rentals(
                    self.state["user_info"].get("city", ""),
                    start_date,
                    end_date,
                    driver_age=self.state["user_info"].get("age", 30)
                )   
                fuel_price = self.info_agent.get_fuel_price(self.state["user_info"].get("city", ""))
                if fuel_price and car_info:
                    print(f"[DEBUG] Successfully got fuel price and car info, fuel_price: {fuel_price}, car_info: {car_info}")
            
            budget = self.route_agent.estimate_budget(
                all_attractions,
                self.state["user_info"],
                self.state["should_rent_car"],
                car_info if self.state["should_rent_car"] else None,
                fuel_price if self.state["should_rent_car"] else None
            )
       
            # Store in state
            self.state["itinerary"] = itinerary
            self.state["budget"] = budget
            
            # Generate confirmation message
            confirmation = self.comm_agent.generate_booking_confirmation(
                itinerary,
                budget,
                self.state["should_rent_car"],
                self.state["user_info"].get("name", "Traveler"),
            )

            # evaluation test
            evaluate_state_with_llm(self.state)
            
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