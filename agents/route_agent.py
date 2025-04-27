import itertools
import math
import json
from datetime import datetime, timedelta
import networkx as nx

class RouteAgent:
    def __init__(self, api_key=None):
        """Initialize RouteAgent with optional API key for distance calculations"""
        self.api_key = api_key
        self.distances_cache = {}
    
    def get_optimal_route(self, spots, start_point=None):
        """Calculate optimal route between selected attractions"""
        if not spots or len(spots) <= 1:
            return spots
        
        # Get distance matrix
        distance_matrix = self._get_distance_matrix(spots)
        
        # Solve TSP (Traveling Salesman Problem)
        if len(spots) <= 5:
            # For small number of points, brute force is fine
            return self._solve_tsp_brute_force(spots, distance_matrix)
        else:
            # For larger problems, use approximate method
            return self._solve_tsp_approximate(spots, distance_matrix)
    
    def _get_distance_matrix(self, spots):
        """Get distance matrix between all pairs of spots"""
        n = len(spots)
        matrix = [[0 for _ in range(n)] for _ in range(n)]
        
        # Fill the matrix with distances
        for i in range(n):
            for j in range(i+1, n):
                # Get distance between spot i and spot j
                distance = self._calculate_distance(spots[i], spots[j])
                matrix[i][j] = distance
                matrix[j][i] = distance  # Symmetric
        
        return matrix
    
    def _calculate_distance(self, spot1, spot2):
        """Calculate distance between two spots using coordinates"""
        # Check if we have location data
        if "location" not in spot1 or "location" not in spot2:
            return 1  # Default distance if no location data
        
        # Check cache first
        cache_key = f"{spot1['id']}_{spot2['id']}"
        if cache_key in self.distances_cache:
            return self.distances_cache[cache_key]
        
        # Calculate straight-line distance (haversine formula)
        lat1, lon1 = spot1["location"]["lat"], spot1["location"]["lng"]
        lat2, lon2 = spot2["location"]["lat"], spot2["location"]["lng"]
        
        R = 6371  # Earth radius in km
        
        # Convert coordinates to radians
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
        
        # Haversine formula
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        distance = R * c
        
        # Cache the result
        self.distances_cache[cache_key] = distance
        
        return distance
    
    def _solve_tsp_brute_force(self, spots, distance_matrix):
        """Solve TSP by trying all permutations (only for small problems)"""
        n = len(spots)
        best_distance = float('inf')
        best_order = list(range(n))
        
        # Try all permutations
        for perm in itertools.permutations(range(n)):
            distance = sum(distance_matrix[perm[i]][perm[i+1]] for i in range(n-1))
            
            if distance < best_distance:
                best_distance = distance
                best_order = perm
        
        # Return spots in optimal order
        return [spots[i] for i in best_order]
    
    def _solve_tsp_approximate(self, spots, distance_matrix):
        """Solve TSP using approximation algorithm (Christofides or nearest neighbor)"""
        # Create a complete graph
        G = nx.Graph()
        n = len(spots)
        
        # Add nodes and edges with distances
        for i in range(n):
            G.add_node(i)
            for j in range(i+1, n):
                G.add_edge(i, j, weight=distance_matrix[i][j])
        
        # Find approximate TSP tour
        tour = nx.approximation.traveling_salesman_problem(G, cycle=True)
        
        # Remove the last node (it's the same as the first to complete the cycle)
        tour = tour[:-1]
        
        # Return spots in calculated order
        return [spots[i] for i in tour]
    
    def generate_itinerary(self, ordered_spots, start_date, num_days):
        """Generate daily itinerary based on ordered spots"""
        itinerary = []
        current_date = datetime.strptime(start_date, "%Y-%m-%d")
        current_day = 1
        current_day_spots = []
        remaining_hours = 8  # 8 hours of activity per day
        
        for spot in ordered_spots:
            spot_duration = spot.get("estimated_duration", 2)
            
            # If this spot doesn't fit in the current day, move to next day
            if spot_duration > remaining_hours:
                # Save current day's itinerary
                if current_day_spots:
                    itinerary.append({
                        "day": current_day,
                        "date": current_date.strftime("%Y-%m-%d"),
                        "spots": current_day_spots
                    })
                
                # Move to next day
                current_day += 1
                current_date += timedelta(days=1)
                current_day_spots = []
                remaining_hours = 8
                
                # Check if we've exceeded the number of days
                if current_day > num_days:
                    break
            
            # Add spot to current day
            spot_with_time = spot.copy()
            hours_spent = remaining_hours - spot_duration
            start_hour = int(9 + (8 - remaining_hours))  # Start at 9 AM
            end_hour = int(start_hour + spot_duration)
            
            spot_with_time["start_time"] = f"{start_hour:02d}:00"
            spot_with_time["end_time"] = f"{end_hour:02d}:00"
            
            current_day_spots.append(spot_with_time)
            remaining_hours -= spot_duration
        
        # Add the last day if not empty
        if current_day_spots:
            itinerary.append({
                "day": current_day,
                "date": current_date.strftime("%Y-%m-%d"),
                "spots": current_day_spots
            })
        
        return itinerary
    
    def estimate_budget(self, spots, user_prefs):
        """Estimate budget for the selected attractions"""
        # Base daily costs
        base_costs = {
            "low": {"accommodation": 50, "food": 30, "transport": 10},
            "medium": {"accommodation": 100, "food": 60, "transport": 20},
            "high": {"accommodation": 200, "food": 100, "transport": 40}
        }
        
        # Get budget level from user preferences
        budget_value = user_prefs.get("budget", "medium")
        
        # Convert budget value to level
        if isinstance(budget_value, str):
            # Remove currency symbols and convert to numeric range
            budget_value = budget_value.replace("$", "").replace(",", "")
            if "–" in budget_value or "-" in budget_value:
                # Take the lower bound of the range
                budget_value = budget_value.split("–")[0].split("-")[0]
            try:
                budget_value = float(budget_value)
                if budget_value < 1000:
                    budget_level = "low"
                elif budget_value < 3000:
                    budget_level = "medium"
                else:
                    budget_level = "high"
            except ValueError:
                budget_level = "medium"
        else:
            budget_level = "medium"
        
        num_people = user_prefs.get("people", 1)
        num_days = user_prefs.get("days", 1)
        
        # Calculate base costs
        daily_cost = sum(base_costs[budget_level].values())
        base_total = daily_cost * int(num_days) * int(num_people)
        
        # Add attraction costs
        attraction_cost = 0
        for spot in spots:
            price_level = spot.get("price_level", 2)
            # Convert price level to actual cost
            cost_map = {0: 0, 1: 10, 2: 20, 3: 30, 4: 50}
            attraction_cost += cost_map.get(price_level, 20) * int(num_people)
        
        # Calculate total
        total = base_total + attraction_cost
        
        # Add car rental if needed
        if user_prefs.get("car_rental", False):
            car_cost_daily = {"low": 30, "medium": 50, "high": 80}
            total += car_cost_daily[budget_level] * int(num_days)
        
        # Return detailed budget
        return {
            "total": total,
            "accommodation": base_costs[budget_level]["accommodation"] * int(num_days) * int(num_people),
            "food": base_costs[budget_level]["food"] * int(num_days) * int(num_people),
            "transport": base_costs[budget_level]["transport"] * int(num_days) * int(num_people),
            "attractions": attraction_cost,
            "car_rental": car_cost_daily[budget_level] * int(num_days) if user_prefs.get("car_rental", False) else 0
        }
    
    # budget估算为什么全部放在route_agent里？是否应该强调交通成本？
    
    # 1. 交通成本估算不够细化
	# •	目前 transport 是固定 daily cost，没有考虑景点之间真实距离
	# •	没有基于 distance_matrix 动态估算路线中的交通成本