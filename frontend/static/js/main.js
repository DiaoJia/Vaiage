document.addEventListener('DOMContentLoaded', function() {
    // Initialize map
    const map = L.map('map').setView([48.8566, 2.3522], 13); // Default to Paris
    
    // Add OpenStreetMap tiles
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(map);

    // Cache DOM elements
    const chatForm = document.getElementById('chat-form');
    const userInput = document.getElementById('user-input');
    const chatContainer = document.getElementById('chat-container');
    const itineraryContainer = document.getElementById('itinerary-container');
    const recommendationsContainer = document.getElementById('recommendations-container');
    const loadingSpinner = document.getElementById('loading-spinner');
    const resetBtn = document.getElementById('reset-btn');
    
    // Store markers for later reference
    let mapMarkers = [];
    
    // Store state
    let state = {
        step: 'chat',
        userInfo: {},
        attractions: [],
        selectedAttractions: [],
        itinerary: null,
        budget: null
    };

    // Handle form submission
    chatForm.addEventListener('submit', function(e) {
        e.preventDefault();
        const message = userInput.value.trim();
        
        if (message) {
            // Add user message to chat
            addChatMessage(message, 'user');
            
            // Clear input
            userInput.value = '';
            
            // Send to backend
            processUserInput(message);
        }
    });
    
    // Reset button
    resetBtn.addEventListener('click', function() {
        resetConversation();
    });
    
    // Add a message to the chat container
    function addChatMessage(message, role) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `chat-message ${role}`;
        
        const messageContent = document.createElement('div');
        messageContent.className = 'message-content';
        messageContent.innerHTML = message;
        
        messageDiv.appendChild(messageContent);
        chatContainer.appendChild(messageDiv);
        
        // Scroll to bottom
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }
    
    // Process user input by sending to backend
    function processUserInput(message) {
        // Show loading spinner
        loadingSpinner.classList.remove('d-none');
        
        // Prepare request payload
        const payload = {
            step: state.step,
            user_input: message
        };
        
        // Add selected attractions if in recommend step
        if (state.step === 'recommend' && state.selectedAttractions.length > 0) {
            payload.selected_attraction_ids = state.selectedAttractions.map(a => a.id);
        }
        
        // Send to backend
        fetch('/api/process', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(payload),
        })
        .then(response => response.json())
        .then(data => {
            // Hide loading spinner
            loadingSpinner.classList.add('d-none');
            
            // Update state
            state.step = data.next_step || state.step;
            
            if (data.state) {
                if (data.state.user_info) state.userInfo = data.state.user_info;
                if (data.state.attractions) state.attractions = data.state.attractions;
                if (data.state.selected_attractions) state.selectedAttractions = data.state.selected_attractions;
                if (data.state.itinerary) state.itinerary = data.state.itinerary;
                if (data.state.budget) state.budget = data.state.budget;
            }
            
            // Add response to chat
            if (data.response) {
                addChatMessage(data.response, 'assistant');
            }
            
            // Update attractions if provided
            if (data.attractions) {
                updateAttractions(data.attractions);
            }
            
            // Update map if map data provided
            if (data.map_data) {
                updateMap(data.map_data);
            }
            
            // Update itinerary if provided
            if (data.itinerary) {
                updateItinerary(data.itinerary);
            }
            
            // Update budget if provided
            if (data.budget) {
                updateBudget(data.budget);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            loadingSpinner.classList.add('d-none');
            addChatMessage('Sorry, there was an error processing your request. Please try again.', 'assistant');
        });
    }
    
    // Update map with new data
    function updateMap(mapData) {
        // Clear existing markers
        mapMarkers.forEach(marker => map.removeLayer(marker));
        mapMarkers = [];
        
        if (mapData && mapData.length > 0) {
            // Center map on first location
            map.setView([mapData[0].lat, mapData[0].lng], 13);
            
            // Add markers for each location
            mapData.forEach(location => {
                // Different colors for different categories
                const colorMap = {
                    "landmark": "red",
                    "museum": "blue",
                    "nature": "green",
                    "entertainment": "purple",
                    "shopping": "orange",
                    "other": "gray"
                };
                
                const iconColor = colorMap[location.category] || "gray";
                
                const marker = L.marker([location.lat, location.lng], {
                    icon: L.divIcon({
                        className: `map-marker marker-${location.category}`,
                        html: `<i class="fas fa-map-marker-alt"></i>`,
                        iconSize: [30, 30]
                    })
                }).addTo(map);
                
                marker.bindTooltip(location.name);
                mapMarkers.push(marker);
            });
            
            // Fit bounds to show all markers
            if (mapMarkers.length > 1) {
                const group = new L.featureGroup(mapMarkers);
                map.fitBounds(group.getBounds().pad(0.1));
            }
        }
    }
    
    // Update attractions display
    function updateAttractions(attractions) {
        recommendationsContainer.innerHTML = '';
        
        if (attractions.length === 0) {
            recommendationsContainer.innerHTML = '<p class="text-center text-muted">No attractions found.</p>';
            return;
        }
        
        attractions.forEach(attraction => {
            const card = document.createElement('div');
            card.className = 'card mb-2';
            
            let priceLevel = '';
            for (let i = 0; i < (attraction.price_level || 0); i++) {
                priceLevel += '💰';
            }
            
            let rating = attraction.rating ? `⭐ ${attraction.rating}` : '';
            
            card.innerHTML = `
                <div class="card-body">
                    <div class="form-check">
                        <input class="form-check-input attraction-checkbox" type="checkbox" 
                               value="${attraction.id}" id="attraction-${attraction.id}">
                        <label class="form-check-label" for="attraction-${attraction.id}">
                            <h6 class="card-title mb-1">${attraction.name}</h6>
                            <p class="card-text mb-1">
                                <small class="text-muted">${attraction.category || 'attraction'}</small>
                                <small class="ms-2">${priceLevel}</small>
                                <small class="ms-2">${rating}</small>
                            </p>
                            <small class="text-muted">${attraction.estimated_duration || 2} hours</small>
                        </label>
                    </div>
                </div>
            `;
            
            recommendationsContainer.appendChild(card);
            
            // Add event listener to checkbox
            const checkbox = card.querySelector('.attraction-checkbox');
            checkbox.addEventListener('change', function() {
                if (this.checked) {
                    // Add to selected attractions
                    state.selectedAttractions.push(attraction);
                    // Add marker to map
                    addMarkerToMap(attraction);
                } else {
                    // Remove from selected attractions
                    state.selectedAttractions = state.selectedAttractions.filter(a => a.id !== attraction.id);
                    // Remove marker from map
                    removeMarkerFromMap(attraction.id);
                }
                // Update map view to show all markers
                updateMapView();
            });
        });
        
        // Add confirm button
        const confirmBtn = document.createElement('button');
        confirmBtn.className = 'btn btn-primary w-100';
        confirmBtn.textContent = 'Confirm Selection';
        confirmBtn.addEventListener('click', function() {
            if (state.selectedAttractions.length > 0) {
                processUserInput('Here are my selected attractions');
            } else {
                addChatMessage('Please select at least one attraction.', 'assistant');
            }
        });
        
        recommendationsContainer.appendChild(confirmBtn);
    }
    
    // Add marker to map
    function addMarkerToMap(attraction) {
        const colorMap = {
            "landmark": "red",
            "museum": "blue",
            "nature": "green",
            "entertainment": "purple",
            "shopping": "orange",
            "other": "gray"
        };
        
        const iconColor = colorMap[attraction.category] || "gray";
        
        const marker = L.marker([attraction.location.lat, attraction.location.lng], {
            icon: L.divIcon({
                className: `map-marker marker-${attraction.category}`,
                html: `<i class="fas fa-map-marker-alt"></i>`,
                iconSize: [30, 30]
            })
        }).addTo(map);
        
        marker.bindTooltip(attraction.name);
        marker.attractionId = attraction.id; // Store attraction ID for later reference
        mapMarkers.push(marker);
    }

    // Remove marker from map
    function removeMarkerFromMap(attractionId) {
        const markerIndex = mapMarkers.findIndex(m => m.attractionId === attractionId);
        if (markerIndex !== -1) {
            map.removeLayer(mapMarkers[markerIndex]);
            mapMarkers.splice(markerIndex, 1);
        }
    }

    // Update map view to show all markers
    function updateMapView() {
        if (mapMarkers.length > 0) {
            const group = new L.featureGroup(mapMarkers);
            map.fitBounds(group.getBounds().pad(0.1));
        }
    }
    
    // Update itinerary display
    function updateItinerary(itinerary) {
        itineraryContainer.innerHTML = '';
        
        if (!itinerary || itinerary.length === 0) {
            itineraryContainer.innerHTML = '<p class="text-center text-muted">No itinerary available yet.</p>';
            return;
        }
        
        itinerary.forEach(day => {
            const dayCard = document.createElement('div');
            dayCard.className = 'card mb-3';
            
            let spotsHTML = '';
            day.spots.forEach(spot => {
                let priceLevel = '';
                for (let i = 0; i < (spot.price_level || 0); i++) {
                    priceLevel += '💰';
                }
                
                spotsHTML += `
                    <div class="card mb-2">
                        <div class="card-body py-2">
                            <h6 class="mb-1">${spot.name}</h6>
                            <p class="mb-0 small">
                                <span class="badge bg-primary">${spot.start_time} - ${spot.end_time}</span>
                                <span class="badge bg-secondary ms-1">${spot.category || 'attraction'}</span>
                                <span class="ms-2">${priceLevel}</span>
                            </p>
                        </div>
                    </div>
                `;
            });
            
            dayCard.innerHTML = `
                <div class="card-header bg-light">
                    <strong>Day ${day.day}</strong> - ${day.date}
                </div>
                <div class="card-body">
                    ${spotsHTML}
                </div>
            `;
            
            itineraryContainer.appendChild(dayCard);
        });
    }
    
    // Update budget display
    function updateBudget(budget) {
        if (!budget) return;
        
        const budgetDiv = document.createElement('div');
        budgetDiv.className = 'mt-4';
        
        budgetDiv.innerHTML = `
            <h5 class="mb-3">Budget Estimate</h5>
            <div class="card">
                <div class="card-body">
                    <div class="row">
                        <div class="col-6">
                            <p class="mb-1"><strong>Total:</strong> $${budget.total}</p>
                            <p class="mb-1"><strong>Accommodation:</strong> $${budget.accommodation}</p>
                            <p class="mb-1"><strong>Food:</strong> $${budget.food}</p>
                        </div>
                        <div class="col-6">
                            <p class="mb-1"><strong>Transport:</strong> $${budget.transport}</p>
                            <p class="mb-1"><strong>Attractions:</strong> $${budget.attractions}</p>
                            ${budget.car_rental ? `<p class="mb-1"><strong>Car Rental:</strong> $${budget.car_rental}</p>` : ''}
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        itineraryContainer.appendChild(budgetDiv);
    }
    
    // Reset conversation
    function resetConversation() {
        fetch('/api/reset')
            .then(() => {
                // Clear UI
                chatContainer.innerHTML = '';
                itineraryContainer.innerHTML = '<p class="text-center text-muted">Your travel plan will appear here once generated.</p>';
                recommendationsContainer.innerHTML = '<p class="text-center text-muted">Recommendations will appear here based on your preferences.</p>';
                
                // Clear map markers
                mapMarkers.forEach(marker => map.removeLayer(marker));
                mapMarkers = [];
                
                // Reset map view
                map.setView([48.8566, 2.3522], 13);
                
                // Reset state
                state = {
                    step: 'chat',
                    userInfo: {},
                    attractions: [],
                    selectedAttractions: [],
                    itinerary: null,
                    budget: null
                };
                
                // Add initial welcome message
                addChatMessage(`
                    Welcome to your Travel AI Assistant! I'll help you plan your perfect trip. Let's start by gathering some information:
                    <ul>
                        <li>Which city would you like to visit?</li>
                        <li>How many days will you stay?</li>
                        <li>What's your budget (low, medium, high)?</li>
                        <li>How many people are traveling?</li>
                        <li>Are you traveling with children, pets, or have any special requirements?</li>
                    </ul>
                `, 'assistant');
            })
            .catch(error => {
                console.error('Error resetting conversation:', error);
            });
    }
});

// Initialize map and related variables
let map;
let markersLayer;
let selectedMarkersLayer;
let currentAttractions = [];
let selectedAttractions = [];

// Initialize map when page loads
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM loaded, initializing map...');
    
    // Check if map container exists
    const mapContainer = document.getElementById('map');
    if (!mapContainer) {
        console.error('Map container not found!');
        return;
    }
    
    try {
        // Initialize map with Tokyo coordinates
        map = L.map('map').setView([35.6762, 139.6503], 13);
        console.log('Map initialized successfully');
        
        // Add OpenStreetMap tiles
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
            maxZoom: 19
        }).addTo(map);
        console.log('Tile layer added successfully');

        // Initialize markers layers
        markersLayer = L.layerGroup().addTo(map);
        selectedMarkersLayer = L.layerGroup().addTo(map);
        console.log('Marker layers initialized successfully');
        
        // Add a test marker
        const testMarker = L.marker([35.6762, 139.6503])
            .bindPopup('Test Marker')
            .addTo(map);
        console.log('Test marker added successfully');
        
    } catch (error) {
        console.error('Error initializing map:', error);
    }
});

// Update map with new data
function updateMap(data) {
    if (!map) return;
    
    // Clear existing markers
    markersLayer.clearLayers();
    
    // Update current attractions
    currentAttractions = data;
    
    // Add new markers
    data.forEach(attraction => {
        const marker = L.marker([attraction.location.lat, attraction.location.lng])
            .bindPopup(`
                <h3>${attraction.name}</h3>
                <p>${attraction.address}</p>
                <p>Rating: ${attraction.rating}</p>
                <button onclick="selectAttraction('${attraction.id}')">Select</button>
            `);
        markersLayer.addLayer(marker);
    });
    
    // Fit map to show all markers
    if (data.length > 0) {
        const bounds = markersLayer.getBounds();
        map.fitBounds(bounds);
    }
}

// Handle attraction selection
function selectAttraction(attractionId) {
    if (!map) return;
    
    // Find the selected attraction
    const attraction = currentAttractions.find(a => a.id === attractionId);
    if (!attraction) return;
    
    // Add to selected attractions if not already selected
    if (!selectedAttractions.some(a => a.id === attractionId)) {
        selectedAttractions.push(attraction);
        updateSelectedAttractionsList();
        
        // Add marker to selected layer
        const marker = L.marker([attraction.location.lat, attraction.location.lng], {
            icon: L.divIcon({
                className: 'selected-marker',
                html: '<div class="selected-marker-inner"></div>',
                iconSize: [20, 20]
            })
        });
        selectedMarkersLayer.addLayer(marker);
    }
}

// Update selected attractions list
function updateSelectedAttractionsList() {
    const list = document.getElementById('selected-attractions');
    if (!list) return;
    
    list.innerHTML = '';
    
    selectedAttractions.forEach(attraction => {
        const li = document.createElement('li');
        li.innerHTML = `
            <div class="attraction-item">
                <h4>${attraction.name}</h4>
                <p>${attraction.address}</p>
                <button onclick="removeAttraction('${attraction.id}')">Remove</button>
            </div>
        `;
        list.appendChild(li);
    });
}

// Remove attraction from selection
function removeAttraction(attractionId) {
    if (!map) return;
    
    const attraction = selectedAttractions.find(a => a.id === attractionId);
    if (!attraction) return;
    
    selectedAttractions = selectedAttractions.filter(a => a.id !== attractionId);
    updateSelectedAttractionsList();
    
    // Remove marker from selected layer
    selectedMarkersLayer.eachLayer(layer => {
        if (layer.getLatLng().equals([attraction.location.lat, attraction.location.lng])) {
            selectedMarkersLayer.removeLayer(layer);
        }
    });
}

// Make functions available globally
window.updateMap = updateMap;
window.selectAttraction = selectAttraction;
window.removeAttraction = removeAttraction;