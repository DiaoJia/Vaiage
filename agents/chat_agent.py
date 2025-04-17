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
        
        # Merge new inputs into state
        if user_input:
            new_info = self.extract_info_from_message(user_input)
            for field, value in new_info.items():
                if value:
                    state[field] = value
        
        # Add user input to conversation
        self.conversation_history.append(HumanMessage(content=user_input))
        
        missing = [f for f in self.required_fields if not state.get(f)]
        if missing:
            prompt = (
                "下面还有一些信息没给我，方便告诉我吗？\n" +
                "\n".join(f"- {field}" for field in missing) +
                "\n您可以一句话补充多个信息。"
            )
            return {"response": prompt, "missing_fields": missing, "complete": False}
        else:
            return {"response": "👌 信息收集完毕，准备为您推荐景点。", "missing_fields": [], "complete": True}
    
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
        

    # 收集信息的过程过于傻缺