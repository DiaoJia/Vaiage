from flask import Flask, render_template, request, jsonify, session
import os
import json
from dotenv import load_dotenv
from workflows.travel_graph import TravelGraph
import uuid
import traceback

# Load environment variables
load_dotenv()

app = Flask(__name__, static_folder="frontend/static", template_folder="frontend/templates")
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "travel-ai-secret")

# Create a session store for workflows
workflows = {}

@app.route('/')
def index():
    """Render the main page"""
    # Initialize a new workflow for this session if needed
    session_id = session.get('session_id', None)
    if not session_id:
        session_id = os.urandom(16).hex()
        session['session_id'] = session_id
        workflows[session_id] = TravelGraph()
    
    return render_template('index.html')

@app.route('/api/process', methods=['POST'])
def process():
    """Process a step in the travel planning workflow"""
    try:
        data = request.json
        session_id = session.get('session_id')
        
        if not session_id:
            # Generate a new session ID if none exists
            session_id = str(uuid.uuid4())
            session['session_id'] = session_id
        
        # Check if workflow exists for this session
        if session_id not in workflows:
            # Create a new workflow and try to load state from database
            workflows[session_id] = TravelGraph(session_id)
        
        workflow = workflows[session_id]
        
        # Debug print current state
        print(f"Current state before processing: {json.dumps(workflow.get_current_state(), ensure_ascii=False)}")
        
        # Process the current step
        step_name = data.get('step', 'chat')
        result = workflow.process_step(step_name, **data)
        
        # Auto-process subsequent steps that don't require user input
        auto_process_steps = ['information', 'strategy']
        next_step = result.get('next_step')
        
        # Only auto-process if user provided input and the next step is in our auto-process list
        if 'user_input' in data and next_step in auto_process_steps:
            print(f"Auto-processing next step: {next_step}")
            
            # Keep processing steps until we reach a step that requires user input
            while next_step in auto_process_steps:
                # Process the next step automatically
                result = workflow.process_step(next_step)
                
                # Update next_step for the next iteration
                next_step = result.get('next_step')
                
                # Break if we've reached a step that requires user input or if completion
                if next_step not in auto_process_steps or next_step == 'complete':
                    break
        
        # Debug print updated state
        print(f"Updated state after processing: {json.dumps(workflow.get_current_state(), ensure_ascii=False)}")
        
        # Add the current state to the result
        result['state'] = workflow.get_current_state()
        
        return jsonify(result)
    except Exception as e:
        # 记录错误并返回友好的错误消息
        print(f"Error processing request: {str(e)}")
        traceback.print_exc()
        return jsonify({
            "error": "处理请求时发生错误，请重试。",
            "details": str(e),
            "response": "抱歉，我遇到了一些问题。请再次告诉我您的旅行计划。"
        }), 500

@app.route('/api/attractions/<city>')
def get_attractions(city):
    """Get attractions for a specific city"""
    session_id = session.get('session_id')
    
    if not session_id or session_id not in workflows:
        return jsonify({"error": "Session not found"}), 404
    
    workflow = workflows[session_id]
    info_agent = workflow.info_agent
    
    attractions = info_agent.get_attractions(city)
    return jsonify(attractions)

@app.route('/api/reset')
def reset_session():
    """Reset the current session"""
    session_id = session.get('session_id')
    
    if session_id and session_id in workflows:
        del workflows[session_id]
    
    session.clear()
    return jsonify({"status": "session reset"})

if __name__ == '__main__':
    # Create data directory if it doesn't exist
    os.makedirs('data', exist_ok=True)
    
    # Create a sample attractions.json file if it doesn't exist
    if not os.path.exists('data/attractions.json'):
        sample_data = {
            "Paris": [
                {
                    "id": "eiffel_tower",
                    "name": "Eiffel Tower",
                    "category": "landmark",
                    "location": {"lat": 48.8584, "lng": 2.2945},
                    "estimated_duration": 3,
                    "price_level": 3
                },
                {
                    "id": "louvre_museum",
                    "name": "Louvre Museum",
                    "category": "museum",
                    "location": {"lat": 48.8606, "lng": 2.3376},
                    "estimated_duration": 4,
                    "price_level": 2
                }
            ],
            "New York": [
                {
                    "id": "central_park",
                    "name": "Central Park",
                    "category": "nature",
                    "location": {"lat": 40.7812, "lng": -73.9665},
                    "estimated_duration": 3,
                    "price_level": 0
                },
                {
                    "id": "empire_state_building",
                    "name": "Empire State Building",
                    "category": "landmark",
                    "location": {"lat": 40.7484, "lng": -73.9857},
                    "estimated_duration": 2,
                    "price_level": 3
                }
            ]
        }
        
        with open('data/attractions.json', 'w') as f:
            json.dump(sample_data, f)
    
    # Run the app
    app.run(debug=True)