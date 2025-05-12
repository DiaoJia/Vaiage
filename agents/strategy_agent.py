import math
import random
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from typing import Generator
import utils
import json
import re

class StrategyAgent:
    def __init__(self, model_name="gpt-4o"):
        """Initialize StrategyAgent with AI model for planning"""
        self.model = ChatOpenAI(model_name=model_name, temperature=0.7, streaming=True)
    
    def plan_remaining_time(self, selected_spots, total_days, all_attractions, user_prefs, weather_summary):
        with open("input of strategy.txt", "w") as f: #for debug
            json.dump({
                "selected_spots": selected_spots,
                "total_days": total_days,
                "all_attractions": all_attractions,
                "user_prefs": user_prefs,
                "weather_summary": weather_summary
            }, f, indent=4)
        print("now in plan_remaining_time")
        try:
            """Calculate remaining time and suggest additional attractions"""
            total_available_hours = int(total_days) * 8 # This seems to be unused if we get a full plan
            selected_data = []
            for spot in selected_spots:
                selected_data.append({
                    "id": spot["id"],
                    "name": spot["name"],
                    "estimated_duration": spot.get("estimated_duration", 2),
                    "location": spot["location"]
                })
            
            all_attractions_data = []
            for spot in all_attractions:
                all_attractions_data.append({
                    "id": spot["id"],
                    "name": spot["name"],
                    "estimated_duration": spot.get("estimated_duration", 2),
                    "location": spot["location"]
                })
            name_to_all_map = {i["name"]:i for i in all_attractions} # Map name to full attraction object
            
            max_try = 5
            final_planned_attractions_names = []
            daily_plan_raw = {}

            user_prefs_str = json.dumps(user_prefs, indent=2, ensure_ascii=False)
            weather_str = weather_summary if weather_summary else "No specific weather summary provided."

            for i in range(max_try):
                prompt = f"""
                You are a travel advisor helping with trip logistics.
                The user is planning a {total_days}-day trip.

                User Preferences:
                {user_prefs_str}

                Weather Summary for the trip period:
                {weather_str}

                Here are the attractions they have pre-selected (must be included in the plan):
                {selected_data}

                Here is a list of all available attractions to choose from (including the pre-selected ones if they appear here too, do not duplicate any attractions):
                {all_attractions_data}

                Please create an optimized daily itinerary for the {total_days} days.
                The plan should distribute the attractions across the days to minimize travel time and ensure a balanced schedule.
                Consider the estimated duration of each attraction. Assume a travel day is about 8 hours.
                The selected attractions MUST be included in your plan.
                
                Pay special attention to the user's preferences and specific needs:
                - Adjust the number and types of attractions based on user's mobility issues, health conditions, or special requirements
                - If traveling with children, include more family-friendly activities and allow for breaks
                - For users with mobility issues, plan fewer attractions per day and minimize walking distances
                - Match attraction selection closely with stated hobbies and interests
                - Adapt to the user's budget level when suggesting attractions
                
                Consider user preferences (e.g., hobbies, pace, budget) and the weather summary when selecting and scheduling attractions. For example, if the weather is rainy, prioritize indoor activities. If the user likes history, include more historical sites.
                After selecting all attractions, consider their locations when creating the daily schedule. Group attractions that are close to each other on the same day to minimize travel time.
                Do not use bold font or any markdown.
                Return the result as a JSON object where keys are "day1", "day2", ..., "dayN" and values are lists of attraction names for that day.
                For example: {{\"day1\": ["Attraction A", "Attraction B"], "day2": ["Attraction C"]}}
                Ensure the output is a valid JSON object only.
                """
                result = utils.ask_openai(prompt)
                print(f"Attempt {i+1} - Raw AI Output: {result}") # Debug raw output
                
                if result and 'answer' in result:
                    raw_answer = result['answer']
                    # Try to extract JSON part if it's embedded in text
                    match = re.search(r'\{.*\}', raw_answer, re.DOTALL)
                    if match:
                        json_str = match.group(0)
                        try:
                            daily_plan_raw = json.loads(json_str)
                            # Validate structure: dict with "dayX" keys and list of strings (names) values
                            if not isinstance(daily_plan_raw, dict) or \
                               not all(isinstance(k, str) and k.startswith("day") and \
                                       isinstance(v, list) and all(isinstance(name, str) for name in v) \
                                       for k, v in daily_plan_raw.items()):
                                print(f"Invalid JSON structure or non-string item in day's list: {daily_plan_raw}")
                                daily_plan_raw = {} # Reset if structure is wrong
                                continue
                            print(f"Successfully parsed daily plan: {daily_plan_raw}")
                        except json.JSONDecodeError as e:
                            print(f"JSON parsing failed on attempt {i+1}: {e}")
                            print(f"Problematic JSON string: {json_str}")
                            daily_plan_raw = {}
                            continue # Try again if parsing fails
                    else:
                        print(f"No JSON object found in AI response on attempt {i+1}: {raw_answer}")
                        daily_plan_raw = {}
                        continue
                else:
                    print(f"No answer from AI on attempt {i+1}")
                    daily_plan_raw = {}
                    continue

                #景点列表: attractions_name
                current_plan_attraction_names = []
                for day_key in sorted(daily_plan_raw.keys()): # Ensure consistent order for validation
                    if isinstance(daily_plan_raw[day_key], list):
                        current_plan_attraction_names.extend(daily_plan_raw[day_key])
                
                # Validation: Check if all selected spots are in the plan
                valid_plan = True
                for selected_spot_info in selected_data:
                    if selected_spot_info["name"] not in current_plan_attraction_names:
                        print(f"Validation Failed: Selected spot '{selected_spot_info['name']}' not in the generated plan {current_plan_attraction_names}.")
                        valid_plan = False
                        break
                
                if valid_plan:
                    final_planned_attractions_names = current_plan_attraction_names
                    print(f"Valid plan found: {daily_plan_raw}")
                    break # Exit loop if a valid plan is found
                else:
                    print(f"Invalid plan on attempt {i+1}, retrying...")

            if not final_planned_attractions_names: # If no valid plan after max_try
                print("Failed to generate a valid plan after multiple attempts. Returning selected spots as fallback.")
                # Fallback: use selected spots if planning fails, or handle error appropriately
                additional_attractions_details = [spot for spot in selected_spots]
            else:
                # Map names back to full attraction details
                additional_attractions_details = []
                for name in final_planned_attractions_names:
                    if name in name_to_all_map:
                        additional_attractions_details.append(name_to_all_map[name])
                    else:
                        # Handle case where a planned attraction name might not be in our initial list (e.g. slight name mismatch from LLM)
                        # For now, we'll just skip it, but ideally, we'd have fuzzy matching or a way to confirm
                        print(f"Warning: Planned attraction '{name}' not found in the provided all_attractions list.")


            # The function needs to return "additional_attractions" which is used later as the primary list of attractions.
            # And "remaining_hours" which seems less critical if the AI does full daily planning.
            return {
                "remaining_hours": total_available_hours, # This might need re-evaluation or can be a dummy value.
                "additional_attractions": additional_attractions_details, # This should be the flat list of all planned attractions.
                "daily_plan": daily_plan_raw # Optionally return the structured daily plan if needed elsewhere
            }
        except Exception as e:
            print(f"Error in plan_remaining_time: {e}")
            import traceback
            traceback.print_exc()
            raise    
    def _suggest_additional_attractions(self, selected_spots, all_attractions, remaining_hours):
        """Suggest additional attractions based on remaining time"""
        # Get IDs of already selected spots
        selected_ids = [spot["id"] for spot in selected_spots]
        
        # Filter out already selected attractions
        available_attractions = [a for a in all_attractions if a["id"] not in selected_ids]
        
        if not available_attractions:
            return []
        
        # Sort by proximity to selected spots (if location data available)
        # This is a simplification - in a real app, you'd use actual distances
        scored_attractions = []
        for attraction in available_attractions:
            # Score based on duration (prefer attractions that fit in remaining time)
            duration = attraction.get("estimated_duration", 2)
            if duration <= remaining_hours:
                scored_attractions.append((attraction, duration))
        
        # Sort by duration (ascending)
        scored_attractions.sort(key=lambda x: x[1])
        # Return attractions that fit within remaining time
        result = []
        total_duration = 0
        for attraction, duration in scored_attractions:
            if total_duration + duration <= remaining_hours:
                result.append(attraction)
                total_duration += duration  
        return result
    
    # 该租车判断逻辑是否合理？是否更应该考虑当地具体的交通情况？
    def should_rent_car(self, selected_spots, city, user_prefs):
        """Determine if car rental is recommended based on selected attractions"""
        # If fewer than 2 spots selected, no need for car
        if len(selected_spots) < 2:
            return False
        
        # Check if any attractions are far from city center
        far_attractions = 0
        for spot in selected_spots:
            # This is simplified - would need actual distance data
            if spot.get("distance_from_center", 0) > 5:  # km
                far_attractions += 1
        
        # If more than half of attractions are far, suggest car rental
        if far_attractions > len(selected_spots) / 2:
            return True
        
        # Check if user has physical limitations
        if user_prefs.get("health") == "limited":
            return True
        
        # Check if user has kids
        if user_prefs.get("kids", False):
            return True
        
        # Check for nature attractions which may be remote
        nature_attractions = [spot for spot in selected_spots if spot.get("category") == "nature"]
        if len(nature_attractions) >= 2:
            return True
        
        return False
    
    def get_ai_recommendation(self, user_prefs, selected_spots, total_days, user_name=None) -> Generator:
        """Get AI recommendation about the overall trip plan"""
        print(f"[DEBUG] Received user_prefs in get_ai_recommendation: {user_prefs}")  # Debug log
        
        # Create prompt for the LLM
        name = user_name if user_name else "Traveler"
        spot_names = [spot["name"] for spot in selected_spots]
        days = total_days
        
        # Extract specific preferences
        people = user_prefs.get('people', 1)
        has_kids = user_prefs.get('kids', 'no').lower() == 'yes'
        health_prefs = user_prefs.get('health', 'good')
        budget = user_prefs.get('budget', 'medium')
        hobbies = user_prefs.get('hobbies', '')
        name = user_prefs.get('name', name)
        should_rent_car = user_prefs.get('should_rent_car', False)
        prompt = f"""
        {name} is planning a {days}-day trip with the following attractions:
        {', '.join(spot_names)}
        
        Their specific preferences are:
        - Number of people: {people}
        - Traveling with children: {'Yes' if has_kids else 'No'}
        - Health/Dietary requirements: {health_prefs}
        - Budget level: {budget}
        - Interests/Hobbies: {hobbies}
        - should_rent_car: {should_rent_car}
        
        Based on these EXACT preferences, please provide recommendations:
        1. Would you recommend renting a car for this itinerary? Why or why not?
        2. What adjustments would you suggest to make the trip more enjoyable given these specific preferences?
        
        IMPORTANT: Make sure your recommendations align with the traveler's actual preferences as listed above.
        For example, if they are not traveling with children, do not suggest child-friendly activities.
        """
        
        messages = [
            SystemMessage(content="You are a travel advisor helping with trip logistics. Always base your recommendations on the exact preferences provided by the traveler.(Call him/her by his/her name)"),
            HumanMessage(content=prompt)
        ]
        
        try:
            return self.model.stream(messages)
        except Exception as e:
            print(f"Error in get_ai_recommendation: {e}")
            return None