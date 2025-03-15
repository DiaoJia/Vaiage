import streamlit as st
import requests
import json
import os
import folium
from streamlit_folium import folium_static

class TravelUI:
    def __init__(self, api_base_url="http://127.0.0.1:5000"):
        """Initialize the Travel UI with API base URL"""
        self.api_base_url = api_base_url
        self.init_session_state()
        
    def init_session_state(self):
        """Initialize session state variables"""
        if 'chat_history' not in st.session_state:
            st.session_state.chat_history = []
        if 'current_step' not in st.session_state:
            st.session_state.current_step = "chat"
        if 'user_info' not in st.session_state:
            st.session_state.user_info = {}
        if 'attractions' not in st.session_state:
            st.session_state.attractions = []
        if 'selected_attractions' not in st.session_state:
            st.session_state.selected_attractions = []
        if 'itinerary' not in st.session_state:
            st.session_state.itinerary = None
        if 'budget' not in st.session_state:
            st.session_state.budget = None
        if 'map_data' not in st.session_state:
            st.session_state.map_data = None
    
    def reset_session(self):
        """Reset the session"""
        requests.get(f"{self.api_base_url}/api/reset")
        for key in st.session_state.keys():
            del st.session_state[key]
        self.init_session_state()
    
    def send_message(self, user_message):
        """Send user message to backend API"""
        payload = {
            "step": st.session_state.current_step,
            "user_input": user_message
        }
        
        # Add selected attractions if we're in the recommend step
        if st.session_state.current_step == "recommend" and st.session_state.selected_attractions:
            payload["selected_attraction_ids"] = [a["id"] for a in st.session_state.selected_attractions]
        
        response = requests.post(f"{self.api_base_url}/api/process", json=payload)
        return response.json()
    
    def display_chat_history(self):
        """Display chat history"""
        for message in st.session_state.chat_history:
            if message["role"] == "user":
                st.chat_message("user").write(message["content"])
            else:
                st.chat_message("assistant").write(message["content"])
    
    def display_map(self, locations=None):
        """Display map with attractions"""
        if not locations and not st.session_state.map_data:
            return
        
        data_to_display = locations or st.session_state.map_data
        
        # Create map centered on the first location or default to Paris
        if data_to_display:
            center_lat = data_to_display[0].get("lat", 48.8566)
            center_lng = data_to_display[0].get("lng", 2.3522)
        else:
            center_lat, center_lng = 48.8566, 2.3522
        
        m = folium.Map(location=[center_lat, center_lng], zoom_start=13)
        
        # Add markers for each location
        for i, location in enumerate(data_to_display):
            tooltip = location.get("name", f"Location {i+1}")
            category = location.get("category", "other")
            
            # Different colors for different categories
            color_map = {
                "landmark": "red",
                "museum": "blue",
                "nature": "green",
                "entertainment": "purple",
                "shopping": "orange",
                "other": "gray"
            }
            
            icon_color = color_map.get(category, "gray")
            
            folium.Marker(
                [location.get("lat", center_lat), location.get("lng", center_lng)],
                tooltip=tooltip,
                icon=folium.Icon(color=icon_color)
            ).add_to(m)
        
        folium_static(m)
    
    def display_attractions(self, attractions):
        """Display list of attractions with selection options"""
        st.subheader("Recommended Attractions")
        
        selected_ids = []
        cols = st.columns(2)
        
        for i, attraction in enumerate(attractions):
            col = cols[i % 2]
            with col:
                is_selected = st.checkbox(
                    f"{attraction['name']} ({attraction.get('category', 'attraction')})",
                    key=f"attr_{attraction['id']}"
                )
                if is_selected:
                    selected_ids.append(attraction["id"])
                
                # Show rating if available
                if "rating" in attraction:
                    st.write(f"⭐ {attraction['rating']}")
                
                # Show price level
                price_level = attraction.get("price_level", 2)
                st.write("💰" * price_level)
                
                # Show duration
                duration = attraction.get("estimated_duration", 1)
                st.write(f"⏱️ {duration} hours")
                
                st.divider()
        
        return selected_ids
    
    def display_itinerary(self, itinerary):
        """Display trip itinerary"""
        st.subheader("Your Travel Itinerary")
        
        for day in itinerary:
            with st.expander(f"Day {day['day']} - {day['date']}"):
                for spot in day.get("spots", []):
                    st.markdown(f"**{spot['name']}** ({spot.get('start_time', '9:00')} - {spot.get('end_time', '11:00')})")
                    st.write(f"Category: {spot.get('category', 'attraction')}")
                    if "price_level" in spot:
                        st.write("Price: " + "💰" * spot.get("price_level", 0))
                    st.divider()
    
    def display_budget(self, budget):
        """Display trip budget breakdown"""
        st.subheader("Budget Estimate")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric("Total Cost", f"${budget['total']}")
            st.metric("Accommodation", f"${budget['accommodation']}")
            st.metric("Food", f"${budget['food']}")
        
        with col2:
            st.metric("Transportation", f"${budget['transport']}")
            st.metric("Attractions", f"${budget['attractions']}")
            if budget.get('car_rental', 0) > 0:
                st.metric("Car Rental", f"${budget['car_rental']}")
    
    def run(self):
        """Run the UI application"""
        st.title("Travel AI Assistant")
        
        # Sidebar
        with st.sidebar:
            st.header("Trip Planning")
            if st.button("Start New Trip"):
                self.reset_session()
                st.rerun()
            
            # Display current user info
            if st.session_state.user_info:
                st.subheader("Your Trip Details")
                for key, value in st.session_state.user_info.items():
                    st.write(f"**{key.capitalize()}:** {value}")
        
        # Main content area
        tab1, tab2, tab3 = st.tabs(["Chat", "Map & Attractions", "Itinerary"])
        
        with tab1:
            # Display chat history
            self.display_chat_history()
            
            # Chat input
            user_input = st.chat_input("Ask about your trip...")
            if user_input:
                st.session_state.chat_history.append({"role": "user", "content": user_input})
                
                with st.spinner("Planning your perfect trip..."):
                    response = self.send_message(user_input)
                    
                    # Update session state
                    st.session_state.current_step = response.get("next_step", st.session_state.current_step)
                    if "state" in response:
                        state = response["state"]
                        st.session_state.user_info = state.get("user_info", st.session_state.user_info)
                    
                    # Save attractions
                    if "attractions" in response:
                        st.session_state.attractions = response["attractions"]
                    
                    # Save map data
                    if "map_data" in response:
                        st.session_state.map_data = response["map_data"]
                    
                    # Save itinerary
                    if "itinerary" in response:
                        st.session_state.itinerary = response["itinerary"]
                    
                    # Save budget
                    if "budget" in response:
                        st.session_state.budget = response["budget"]
                    
                    # Add response to chat history
                    st.session_state.chat_history.append({
                        "role": "assistant", 
                        "content": response.get("response", "I'm processing your request.")
                    })
                
                st.rerun()
        
        with tab2:
            col1, col2 = st.columns([2, 3])
            
            with col1:
                if st.session_state.attractions:
                    selected_ids = self.display_attractions(st.session_state.attractions)
                    
                    # Save selected attractions
                    if st.button("Confirm Selection"):
                        selected_attractions = [a for a in st.session_state.attractions if a["id"] in selected_ids]
                        st.session_state.selected_attractions = selected_attractions
                        
                        # Send selection to backend
                        with st.spinner("Optimizing your itinerary..."):
                            response = self.send_message("Here are my selected attractions")
                            
                            # Update session state
                            st.session_state.current_step = response.get("next_step", st.session_state.current_step)
                            
                            # Add response to chat history
                            st.session_state.chat_history.append({
                                "role": "assistant", 
                                "content": response.get("response", "I'm processing your selections.")
                            })
                        
                        st.rerun()
            
            with col2:
                st.subheader("Attractions Map")
                self.display_map()
        
        with tab3:
            if st.session_state.itinerary:
                self.display_itinerary(st.session_state.itinerary)
                
                if st.session_state.budget:
                    self.display_budget(st.session_state.budget)
            else:
                st.info("Complete your trip planning to see your itinerary here.")

if __name__ == "__main__":
    ui = TravelUI()
    ui.run()