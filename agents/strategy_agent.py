import math
import random
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from typing import Generator
import utils
import json
import re

class StrategyAgent:
    def __init__(self, model_name="gpt-3.5-turbo"):
        """Initialize StrategyAgent with AI model for planning"""
        self.model = ChatOpenAI(model_name=model_name, temperature=0.7, streaming=True)
    
    def plan_remaining_time(self, selected_spots, total_days, all_attractions):
        with open("input of strategy.txt", "w") as f: #for debug
            json.dump({
                "selected_spots": selected_spots,
                "total_days": total_days,
                "all_attractions": all_attractions
            }, f, indent=4)
        print("now in plan_remaining_time")
        try:
            """Calculate remaining time and suggest additional attractions"""
            total_available_hours = int(total_days) * 8
            selected = []
            for spot in selected_spots:
                selected.append({
                    "id": spot["id"],
                    "name": spot["name"],
                    "estimated_duration": spot.get("estimated_duration", 2),
                    "location": spot["location"]
                })
            all = []
            for spot in all_attractions:
                all.append({
                    "id": spot["id"],
                    "name": spot["name"],
                    "estimated_duration": spot.get("estimated_duration", 2),
                    "location": spot["location"]
                })
            name_to_all = {i["name"]:i for i in all_attractions}
            max_try = 5
            for i in range(max_try):
                prompt = f"""
                You are a travel advisor helping with trip logistics.
                here are the selected attractions,you must add it in the list of attractions.
                {selected}
                here are the total days for the trip.
                {total_days}
                here are the remaining attractions.
                {all}
                please give me the best route to visit the attractions.don't duplicate the attractions.
                the order of the attractions should minimize the total travel distance.
                result should be a list of attractions name.
                The selected attractions must be in the result.
                Do not use bold font.
                Only return a plain Python list of attraction names, e.g. ["name1", "name2", "name3"]
                
                """
                result = utils.ask_openai(prompt)
                print(result)
                with open("result of strategy.txt", "w") as f: #for debug
                    json.dump(result, f, indent=4)
                attractions_name = []
                with open("result of strategy.txt", "r") as f:
                    data = json.load(f)
                    answer = data['answer']
                    # 用正则提取第一个中括号及其内容
                    match = re.search(r'\[.*\]', answer, re.DOTALL)
                    if match:
                        try:
                            attractions_name = json.loads(match.group())
                        except Exception as e:
                            print("json.loads解析失败:", e)
                            attractions_name = []
                    else:
                        print("未找到合法的列表格式")
                        attractions_name = []
                    print("景点列表:", attractions_name)

                #检验合法性
                valid = True
                for i in selected:
                    if i["name"] not in attractions_name:
                        print(f"selected {i['name']} not in attractions_name")
                        valid = False
                        break
                if not valid:
                    continue
                if valid:
                    additional_attractions = [name_to_all[i] for i in attractions_name if i in name_to_all.keys()]
                    break
            
            return {
                "remaining_hours": total_available_hours, #随意吧
                "additional_attractions": additional_attractions #其实就是attractions
            }
        except Exception as e:
            print("Error in plan_remaining_time:", e)
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