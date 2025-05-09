import math
import random
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from typing import Generator

class StrategyAgent:
    def __init__(self, model_name="gpt-3.5-turbo"):
        """Initialize StrategyAgent with AI model for planning"""
        self.model = ChatOpenAI(model_name=model_name, temperature=0.7, streaming=True)
    
    def plan_remaining_time(self, selected_spots, total_days, all_attractions):
        """Calculate remaining time and suggest additional attractions"""
        # Calculate how much time selected attractions will take
        total_hours_needed = sum([spot.get("estimated_duration", 2) for spot in selected_spots])
        
        # Assume 8 hours of activity per day
        total_available_hours = int(total_days) * 8
        remaining_hours = total_available_hours - total_hours_needed
        

        # If we have more than 4 hours left, suggest additional attractions
        # 是否改为 3h ？
        additional_attractions = []
        if remaining_hours > 4:
            additional_attractions = self._suggest_additional_attractions(
                selected_spots, 
                all_attractions, 
                remaining_hours
            )
        
        return {
            "remaining_hours": remaining_hours,
            "additional_attractions": additional_attractions
        }
    
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
            
            # Stop once we've suggested 3 additional attractions
            if len(result) >= 3:
                break
        
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
        
        prompt = f"""
        {name} is planning a {days}-day trip with the following attractions:
        {', '.join(spot_names)}
        
        Their specific preferences are:
        - Number of people: {people}
        - Traveling with children: {'Yes' if has_kids else 'No'}
        - Health/Dietary requirements: {health_prefs}
        - Budget level: {budget}
        - Interests/Hobbies: {hobbies}
        
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