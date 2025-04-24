import json
import random
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

class RecommendAgent:
    def __init__(self, model_name="gpt-3.5-turbo"):
        """Initialize RecommendAgent with AI model for personalized recommendations"""
        self.model = ChatOpenAI(model_name=model_name, temperature=0.7)
        
    def recommend_core_attractions(self, user_prefs, attractions, max_attractions=5):
        """Recommend attractions based on user preferences"""
        # If no attractions or user preferences, return empty list
        if not attractions or not user_prefs:
            return []

        # Create prompt for the LLM to rank attractions
        prompt = self._create_recommendation_prompt(user_prefs, attractions)
        
        # Ask the LLM to rank attractions
        messages = [
            SystemMessage(content="You are a travel recommendation expert. Rank attractions based on user preferences."),
            HumanMessage(content=prompt)
        ]
        
        response = self.model(messages)
        
        # Parse the response to get ranked attractions
        try:
            # Try to parse JSON response
            ranked_attractions = json.loads(response.content)
        except json.JSONDecodeError:
            # Fallback to simple scoring if LLM doesn't return valid JSON
            ranked_attractions = self._score_attractions(user_prefs, attractions)
        
        # Return top N attractions
        return ranked_attractions[:max_attractions]
    
    def _create_recommendation_prompt(self, user_prefs, attractions):
        """Create prompt for the LLM to rank attractions"""
        attractions_str = json.dumps(attractions, indent=2)
        user_prefs_str = json.dumps(user_prefs, indent=2)
        
        return f"""
        Given the following user preferences and attractions, rank the attractions from most suitable to least suitable.
        
        User preferences:
        {user_prefs_str}
        
        Attractions:
        {attractions_str}
        
        Consider the following factors:
        1. Match between user's hobbies and attraction categories
        2. Physical accessibility based on user's health status
        3. Suitability for children if the user is traveling with kids
        4. Budget constraints
        
        
        Return a list of attraction IDs, ranked from most to least recommended, in this format:
        [
          "attraction_id_1",
          "attraction_id_2",
          ...
        ]
        """
    # 考虑到LLM可能会根据用户的hobbies清一色地推荐某个类别的景点，我们考虑纳入第五个因素：category相对均衡性

    # 考虑后备是一个很好的想法
    def _score_attractions(self, user_prefs, attractions):
        """Score attractions based on user preferences (fallback method)"""
        scored_attractions = []
        
        for attraction in attractions:
            score = 0
            
            # Score based on category match
            if "hobbies" in user_prefs and attraction.get("category") in user_prefs["hobbies"]:
                score += 3
            
            # Score based on health considerations
            if "health" in user_prefs:
                if user_prefs["health"] == "excellent":
                    score += 1  # Any attraction is fine
                elif user_prefs["health"] == "good" and attraction.get("estimated_duration", 3) <= 3:
                    score += 1  # Prefer shorter duration attractions
                elif user_prefs["health"] == "limited" and attraction.get("estimated_duration", 3) <= 2:
                    score += 1  # Strongly prefer shorter attractions
            
            # Score based on budget
            if "budget" in user_prefs:
                budget_level = {"low": 1, "medium": 2, "high": 3}.get(user_prefs["budget"], 2)
                if attraction.get("price_level", 2) <= budget_level:
                    score += 1
            
            # Score based on kids
            if user_prefs.get("kids", False) and attraction.get("kid_friendly", False):
                score += 1
            
            scored_attractions.append((attraction["id"], score, attraction))
        
        # Sort by score (descending)
        # 有点类似于beam search的效果
        scored_attractions.sort(key=lambda x: x[1], reverse=True)
        
        # Return sorted attractions (full objects)
        return [item[2] for item in scored_attractions]
    
    def generate_map_data(self, attractions):
        """Generate map data for frontend visualization"""
        map_data = []
        
        for attraction in attractions:
            map_data.append({
                "id": attraction["id"],
                "name": attraction["name"],
                "lat": attraction["location"]["lat"],
                "lng": attraction["location"]["lng"],
                "category": attraction["category"]
            })
        
        return map_data
    
    def get_attraction_details(self, attraction_id, attractions):
        """Get detailed information about a specific attraction"""
        for attraction in attractions:
            if attraction["id"] == attraction_id:
                return attraction
        
        return None
    

    # 缓存 LLM 推荐结果（结合 hash(user_prefs+city)）
	# •	避免重复算同一个用户偏好组合
    # •	用户多次点击"推荐核心景点"
	# •	相同用户偏好和城市，结果应该是一样的
	# •	但 LLM 每次都重新调用，慢而且贵

    # 所以我们可以对同一请求进行缓存 —— 相同输入 → 不再重复推理 → 返回缓存结果。