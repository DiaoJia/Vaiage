from langchain.chat_models import ChatOpenAI
from langchain.schema import SystemMessage, HumanMessage

class CommunicationAgent:
    def __init__(self, model_name="gpt-3.5-turbo"):
        """Initialize CommunicationAgent with AI model for communication"""
        self.model = ChatOpenAI(model_name=model_name, temperature=0.7)
    
    def post_car_rental_request(self, location, duration, user_prefs):
        """Generate car rental request post"""
        prompt = f"""
        Generate a car rental request post for the following trip:
        
        Location: {location}
        Duration: {duration} days
        Number of people: {user_prefs.get('people', 1)}
        Kids: {'Yes' if user_prefs.get('kids', False) else 'No'}
        Budget level: {user_prefs.get('budget', 'medium')}
        
        The post should be polite, clear, and include all necessary information.
        Include any special requirements such as child seats if needed.
        """
        
        messages = [
            SystemMessage(content="You are a helpful assistant creating a car rental request post."),
            HumanMessage(content=prompt)
        ]
        
        response = self.model(messages)
        
        return {
            "post_content": response.content,
            "location": location,
            "duration": duration,
            "status": "pending"
        }
    
    def handle_rental_response(self, rental_post, response_message):
        """Handle response to car rental request"""
        prompt = f"""
        A car rental company has responded to the following car rental request:
        
        Original request:
        {rental_post['post_content']}
        
        Their response:
        {response_message}
        
        Please draft a polite reply that:
        1. Thanks them for their response
        2. Asks any necessary follow-up questions about pricing, car type, pickup details, etc.
        3. Is friendly and professional
        """
        
        messages = [
            SystemMessage(content="You are a helpful assistant handling communications about car rentals."),
            HumanMessage(content=prompt)
        ]
        
        response = self.model(messages)
        
        return {
            "reply_content": response.content,
            "original_post": rental_post,
            "response_message": response_message
        }
    
    def generate_booking_confirmation(self, itinerary, budget_estimate, car_rental=None):
        """Generate booking confirmation message"""
        itinerary_summary = f"{len(itinerary)} days, starting on {itinerary[0]['date']}"
        attractions_count = sum(len(day['spots']) for day in itinerary)
        
        prompt = f"""
        Generate a friendly, comprehensive trip confirmation message with the following details:
        
        Itinerary: {itinerary_summary}
        Number of attractions: {attractions_count}
        Estimated budget: ${budget_estimate['total']}
        Car rental: {'Yes' if car_rental else 'No'}
        
        The message should:
        1. Confirm the booking is complete
        2. Summarize the trip details
        3. Mention that a detailed itinerary is attached
        4. Provide any useful tips for preparation
        5. Be friendly and excited about their upcoming trip
        """
        
        messages = [
            SystemMessage(content="You are a travel assistant sending a trip confirmation message."),
            HumanMessage(content=prompt)
        ]
        
        response = self.model(messages)
        
        return response.content