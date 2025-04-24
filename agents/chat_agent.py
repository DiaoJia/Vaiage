import os
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
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
        
        # Merge new inputs into state
        if user_input and user_input.strip():
            new_info = self.extract_info_from_message(user_input)
            for field, value in new_info.items():
                if value:
                    state[field] = value
                    print(f"Updated state: {field} = {value}")  # Debug log
        
        # Add user input to conversation if not empty
        if user_input and user_input.strip():
            self.conversation_history.append(HumanMessage(content=user_input))
        
        # Get AI response based on current state and conversation history
        messages = self.conversation_history.copy()
        messages.append(SystemMessage(content=f"""
        Current state: {json.dumps(state, ensure_ascii=False)}
        Required fields: {json.dumps(self.required_fields, ensure_ascii=False)}
        Missing fields: {json.dumps([f for f in self.required_fields if not state.get(f)], ensure_ascii=False)}
        Please help the user complete the missing information in a natural way.
        Remember to acknowledge information that has already been provided.
        """))
        
        try:
            response = self.model(messages)
            self.conversation_history.append(AIMessage(content=response.content))
        except Exception as e:
            print(f"Error getting AI response: {e}")
            response = AIMessage(content="抱歉，我遇到了一些问题。请再试一次。")
        
        missing = [f for f in self.required_fields if not state.get(f)]
        if missing:
            return {
                "response": response.content,
                "missing_fields": missing,
                "complete": False,
                "state": state.copy()  # Return a copy of the state
            }
        else:
            return {
                "response": response.content,
                "missing_fields": [],
                "complete": True,
                "state": state.copy()  # Return a copy of the state
            }
    
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
        
        system_prompt = f"""Extract the following travel information from the user's message and return JSON.
        Carefully analyze the message to understand both explicit and implicit information.
        
        For example, if the user says "without kids" or "no children", set "kids" to "no".
        If they mention "all adults", also set "kids" to "no".
        If they mention family with children, set "kids" to "yes".
        
        Pay attention to negations and context. Don't just look for keywords, understand the meaning.
        
        Return the following JSON structure:
        {{
        {', '.join([f'"{field}": ""' for field in self.required_fields])}
        }}
        
        If any field is missing or unclear, leave it as an empty string.
        """
        
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
        

    