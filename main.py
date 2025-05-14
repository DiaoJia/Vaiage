from flask import Flask, render_template, request, jsonify, session, send_from_directory, send_file, Response
from flask_session import Session
import os
import json
from dotenv import load_dotenv
from workflows.travel_graph import TravelGraph
import requests
import time

# Load environment variables
load_dotenv()

app = Flask(__name__, static_folder="frontend/static", template_folder="frontend/templates")
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "travel-ai-secret")

# Configure session
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = 3600  # 1 hour
app.config['SESSION_COOKIE_SECURE'] = False
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Initialize Flask-Session
Session(app)

# Add static file configuration
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0  # Disable caching
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Create a session store for workflows
workflows = {}

@app.route('/test-image')
def test_image():
    return send_file('frontend/static/images/background.jpg', mimetype='image/jpeg')

@app.route('/static/images/<path:filename>')
def serve_image(filename):
    return send_from_directory('frontend/static/images', filename)

@app.route('/')
def index():
    """Render the main page"""
    # Initialize a new workflow for this session if needed
    session_id = session.get('session_id', None)
    if not session_id:
        session_id = os.urandom(16).hex()
        session['session_id'] = session_id
        workflows[session_id] = TravelGraph()
        print(f"[DEBUG] Created new session: {session_id}")
    else:
        print(f"[DEBUG] Using existing session: {session_id}")
    
    # Load popular attractions
    try:
        with open('frontend/data/popular_attractions.json', 'r') as f:
            popular_attractions = json.load(f)
    except FileNotFoundError:
        popular_attractions = []
    
    return render_template('index.html', popular_attractions=popular_attractions)

@app.route('/api/process', methods=['POST'])
def process():
    """Process a step in the travel planning workflow"""
    try:
        data = request.json
        session_id = session.get('session_id')

        if not session_id:
            session_id = os.urandom(16).hex()
            session['session_id'] = session_id
            workflows[session_id] = TravelGraph()
            print(f"[DEBUG] Created new session: {session_id}")
        else:
            print(f"[DEBUG] Using existing session: {session_id}")
        if session_id not in workflows:
            workflows[session_id] = TravelGraph()
            print(f"[DEBUG] Recreated workflow for session: {session_id}")
        workflow = workflows[session_id]
        # 只保留关键步骤信息
        print(f"[DEBUG] Processing step: {data.get('step', 'chat')} for session: {session_id}")
        # Process the current step
        step_name = data.get('step', 'chat')
        result = workflow.process_step(step_name, **data)
        # Add the current state to the result
        result['state'] = workflow.get_current_state()
        return jsonify(result)
    except Exception as e:
        print(f"[ERROR] in process route: {str(e)}")
        return jsonify({"error": str(e)}), 500

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

@app.route('/api/stream')
def stream():
    """Handle streaming responses"""
    session_id = session.get('session_id')
    if not session_id:
        session_id = os.urandom(16).hex()
        session['session_id'] = session_id
        workflows[session_id] = TravelGraph()
        print(f"[DEBUG] Created new session: {session_id}")
    else:
        print(f"[DEBUG] Using existing session: {session_id}")
    if session_id not in workflows:
        workflows[session_id] = TravelGraph()
        print(f"[DEBUG] Recreated workflow for session: {session_id}")
    workflow = workflows[session_id]
    # 只保留关键步骤信息
    print(f"[DEBUG] Streaming step for session: {session_id}")
    # Get parameters from request
    step_name = request.args.get('step', 'chat')
    user_input = request.args.get('user_input', '')
    selected_attraction_ids = request.args.get('selected_attraction_ids')
    if selected_attraction_ids:
        try:
            selected_attraction_ids = json.loads(selected_attraction_ids)
        except json.JSONDecodeError:
            selected_attraction_ids = None
            
    # Check if the user is confirming satisfaction with the recommendation
    satisfaction_message = 'satisfied with your recommendation' in user_input.lower()
    
    if satisfaction_message:
        print(f"[CRITICAL] Detected satisfaction message: '{user_input}'")
    
    def generate():
        try:
            # Process the step
            result = workflow.process_step(
                step_name, 
                user_input=user_input,
                selected_attraction_ids=selected_attraction_ids
            )
            
            # Check the should_rent_car status right after processing
            current_should_rent_car = workflow.get_current_state().get('should_rent_car', False)
            print(f"[CRITICAL] After processing step, should_rent_car = {current_should_rent_car}")
            
            # Handle streaming response
            if 'stream' in result and result['stream']:
                for chunk in result['stream']:
                    if chunk.content:
                        yield f"data: {{\"type\": \"chunk\", \"content\": {json.dumps(chunk.content)} }}\n\n"
                        time.sleep(0.01)
            
            # Send completion data
            completion_data = {
                'type': 'complete',
                'next_step': result.get('next_step'),
                'missing_fields': result.get('missing_fields', []),
                'state': result.get('state'),
                'attractions': result.get('attractions'),
                'map_data': result.get('map_data'),
                'itinerary': result.get('itinerary'),
                'budget': result.get('budget'),
                'response': result.get('response'),
                'optimal_route': result.get('optimal_route'),
                'rental_post': result.get('rental_post')
            }
            
            # Only override next_step in specific cases
            if step_name == 'strategy':
                current_state = workflow.get_current_state()
                ai_recommendation_generated = current_state.get('ai_recommendation_generated', False)
                should_rent_car = current_state.get('should_rent_car', False)
                
                print(f"[CRITICAL] In stream endpoint, strategy step: ai_recommendation_generated={ai_recommendation_generated}, should_rent_car={should_rent_car}, satisfaction_message={satisfaction_message}")
                
                # If the AI has provided recommendations (whether through initial selection or satisfaction confirmation)
                if ai_recommendation_generated or satisfaction_message:
                    # IMPORTANT: Double-check the should_rent_car value from the current state
                    next_step = 'communication' if should_rent_car else 'route'
                    completion_data['next_step'] = next_step
                    print(f"[CRITICAL] Setting next_step to '{next_step}' based on should_rent_car={should_rent_car}")
                    
                    # Add explicit note about car recommendation decision
                    if should_rent_car:
                        print("[CRITICAL] Car rental IS recommended - moving to communication step")
                    else:
                        print("[CRITICAL] Car rental is NOT recommended - skipping directly to route step")
                
            yield f"data: {json.dumps(completion_data)}\n\n"
            
            # Verify the final decision after sending the completion data
            final_next_step = completion_data.get('next_step')
            print(f"[CRITICAL] Final decision: next_step = {final_next_step}, should_rent_car = {workflow.get_current_state().get('should_rent_car', False)}")
            
        except Exception as e:
            print(f"[ERROR] in stream route: {str(e)}")
            yield f"data: {{\"type\": \"error\", \"error\": {json.dumps(str(e))} }}\n\n"
    return Response(generate(), mimetype='text/event-stream')

@app.route('/api/nearby/<attraction_id>')
def get_nearby_places(attraction_id):
    """Get nearby restaurants and street information for an attraction"""
    session_id = session.get('session_id')
    
    if not session_id or session_id not in workflows:
        return jsonify({"error": "Session not found"}), 404
    
    workflow = workflows[session_id]
    info_agent = workflow.info_agent
    
    # Parse coordinates from attraction_id
    try:
        lat_str, lng_str = attraction_id.split(',')
        lat, lng = float(lat_str), float(lng_str)
    except Exception:
        return jsonify({"error": "Invalid coordinates format. Use 'lat,lng'."}), 400
    
    try:
        result = info_agent.search_nearby_places(lat, lng)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": f"Failed to get nearby places: {str(e)}"}), 500
    
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
    app.run(host="127.0.0.1", port=8000, debug=False)
