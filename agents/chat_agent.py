import os
from langchain_openai import ChatOpenAI

from langchain.schema import SystemMessage, HumanMessage, AIMessage
import json
class ChatAgent:
    def __init__(self, model_name="gpt-3.5-turbo"):
        """Initialize the ChatAgent with specified model"""
        self.model = ChatOpenAI(model_name=model_name, temperature=0.7)
        self.required_fields = ["city", "days", "budget", "people", "kids", "health", "hobbies"]
        self.conversation_history = []
        
    def _init_system_message(self):
        """Initialize system message for the conversation"""
        return SystemMessage(content="""
        You are a helpful travel assistant. Your job is to collect information about the user's travel plans.
        Be friendly, conversational, and help the user plan their trip. Collect all necessary information.
        """)
        
    def collect_info(self, user_input, state=None):
        """Check for missing information and ask user questions to complete the required information"""
        if state is None:
            state = {}
        
        # Initialize conversation if it's empty
        if not self.conversation_history:
            self.conversation_history.append(self._init_system_message())
        
        # Add user input to conversation
        self.conversation_history.append(HumanMessage(content=user_input))
        
        # Identify missing fields
        missing_fields = [field for field in self.required_fields if field not in state or not state[field]]
        
        if missing_fields:
            # Create a prompt to collect missing information
            prompt = f"I need to collect some more information for your trip. Could you please tell me about: {', '.join(missing_fields)}?"
            
            # Generate response using LLM
            self.conversation_history.append(AIMessage(content=prompt))
            return {"response": prompt, "missing_fields": missing_fields, "complete": False}
        
        # If all information is collected
        self.conversation_history.append(AIMessage(content="Great! I have all the information I need."))
        return {"response": "Information collection complete", "missing_fields": [], "complete": True}
    
    def interact_with_user(self, message, state=None):
        """Process user message and generate a response"""
        if state is None:
            state = {}
            
        # Add user message to conversation
        self.conversation_history.append(HumanMessage(content=message))
        
        # Generate response based on the conversation history
        response = self.model(self.conversation_history)
        
        # Add assistant response to conversation history
        self.conversation_history.append(AIMessage(content=response.content))
        
        return response.content
    
    def extract_info_from_message(self, message):
        """Use LLM to extract structured travel information from user message"""

       
        field_list = ', '.join(self.required_fields)  
        system_prompt = f"""Extract the following travel information from the user's message and return JSON:
    {{
    {', '.join([f'"{field}": ""' for field in self.required_fields])}
    }}
    If any field is missing, leave it as an empty string."""

        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=message)
        ]

        try:
            llm_response = self.model.invoke(messages)
            #print("LLM response:", llm_response.content)

            extracted_info = json.loads(llm_response.content)

            filtered_info = {field: extracted_info.get(field, "") for field in self.required_fields}

            return filtered_info 
        except Exception as e:
            print("Error parsing LLM output:", e)
            return {field: "" for field in self.required_fields}