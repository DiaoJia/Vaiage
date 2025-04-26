document.addEventListener('DOMContentLoaded', function() {
    // Initialize map
    const mapContainer = document.getElementById('map');
    if (!mapContainer) {
        console.error('Map container not found!');
        return;
    }

    let map;
    let markersLayer = L.layerGroup();  // Initialize markers layer
    try {
        map = L.map('map').setView([0, 0], 2); // Default to Paris
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap> contributors',
            maxZoom: 19
        }).addTo(map);
        markersLayer.addTo(map);  // Add markers layer to map
        console.log('Map initialized successfully');
    } catch (error) {
        console.error('Error initializing map:', error);
    }

    // Cache DOM elements
    const chatForm = document.getElementById('chat-form');
    const userInput = document.getElementById('user-input');
    const chatContainer = document.getElementById('chat-container');
    const itineraryContainer = document.getElementById('itinerary-container');
    const recommendationsContainer = document.getElementById('recommendations-container');
    const loadingSpinner = document.getElementById('loading-spinner');
    const resetBtn = document.getElementById('reset-btn');
    const stepNav = document.getElementById('step-nav');
    const missingFieldsContainer = document.getElementById('missing-fields');
    const selectedAttractionsList = document.getElementById('selected-attractions');

    // Initialize marker layers
    let selectedMarkersLayer = L.layerGroup().addTo(map);
    let currentAttractions = [];
    let selectedAttractions = [];

    // Auto-scroll for popular attractions
    function initAutoScroll() {
        const scrollContainer = document.querySelector('.scroll-container');
        if (scrollContainer) {
            console.log('Scroll container found, initializing auto-scroll');
            // Duplicate content for seamless looping
            scrollContainer.innerHTML += scrollContainer.innerHTML;

            let scrollSpeed = 1; // Pixels per frame
            let animationFrame;
            let isPaused = false;

            function autoScroll() {
                if (!isPaused) {
                    scrollContainer.scrollTop += scrollSpeed;
                    if (scrollContainer.scrollTop >= scrollContainer.scrollHeight / 2) {
                        scrollContainer.scrollTop = 0;
                    }
                }
                animationFrame = requestAnimationFrame(autoScroll);
            }

            // Pause on hover
            scrollContainer.addEventListener('mouseenter', () => {
                isPaused = true;
            });

            // Resume on mouse leave
            scrollContainer.addEventListener('mouseleave', () => {
                isPaused = false;
            });

            // Start scrolling
            autoScroll();
        } else {
            console.log('Scroll container not found');
        }
    }

    // Use MutationObserver to detect .scroll-container dynamically
    const observer = new MutationObserver((mutations) => {
        if (document.querySelector('.scroll-container')) {
            initAutoScroll();
            observer.disconnect(); // Stop observing once found
        }
    });
    observer.observe(document.body, { childList: true, subtree: true });

    // Update step navigation highlighting
    function updateStepNav(step) {
        if (!stepNav) {
            console.log('Step navigation not found, skipping update');
            return;
        }
        const links = stepNav.querySelectorAll('.nav-link');
        links.forEach(link => {
            if (link.dataset.step === step) {
                link.classList.add('active');
            } else {
                link.classList.remove('active');
            }
        });
    }
    // Show missing fields list
    function showMissingFields(fields) {
        if (!missingFieldsContainer) {
            console.log('Missing fields container not found, skipping update');
            return;
        }
        missingFieldsContainer.innerHTML = '<strong>Additional information needed: </strong>' +
            fields.map(f => `<span class="badge bg-warning text-dark me-1">${f}</span>`).join('');
        missingFieldsContainer.classList.remove('d-none');
    }
    
    // Hide missing fields alert
    function hideMissingFields() {
        missingFieldsContainer.classList.add('d-none');
    }
    
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
            // Update step navigation
            if (data.next_step) {
                updateStepNav(data.next_step);
            }
            // Display or hide missing fields
            if (data.missing_fields && data.missing_fields.length > 0) {
                showMissingFields(data.missing_fields);
            } else {
                hideMissingFields();
            }
            
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
    function updateMap(data) {
        if (!map) return;
        markersLayer.clearLayers();
        currentAttractions = data;

        if (!data || !Array.isArray(data)) {
            console.error('Invalid map data:', data);
            return;
        }

        let bounds = L.latLngBounds([]);  // Initialize empty bounds
        let validMarkers = 0;

        data.forEach(attraction => {
            if (!attraction || !attraction.location || 
                typeof attraction.location.lat !== 'number' || 
                typeof attraction.location.lng !== 'number') {
                console.error('Invalid attraction data:', attraction);
                return;
            }

            const marker = L.marker([attraction.location.lat, attraction.location.lng])
                .bindPopup(`
                    <h3>${attraction.name || 'Unknown'}</h3>
                    <p>${attraction.address || 'No address available'}</p>
                    <p>Rating: ${attraction.rating || 'No rating'}</p>
                    <button onclick="selectAttraction('${attraction.id || ''}')">Select</button>
                `);
            markersLayer.addLayer(marker);
            bounds.extend([attraction.location.lat, attraction.location.lng]);
            validMarkers++;
        });

        // Only fit bounds if we have valid markers
        if (validMarkers > 0) {
            try {
                map.fitBounds(bounds.pad(0.1));
            } catch (error) {
                console.error('Error fitting map bounds:', error);
                // Fallback to default view if bounds fitting fails
                map.setView([48.8566, 2.3522], 13);
            }
        } else {
            // If no valid markers, reset to default view
            map.setView([48.8566, 2.3522], 13);
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
                        <li>What type of activities do you enjoy (e.g., adventure, relaxation, culture)?</li>
                        <li>What's your health condition?</li>
                    </ul>
                `, 'assistant');
            })
            .catch(error => {
                console.error('Error resetting conversation:', error);
            });
    }
    // Handle attraction selection
    function selectAttraction(attractionId) {
        if (!map) return;
        const attraction = currentAttractions.find(a => a.id === attractionId);
        if (!attraction) return;

        if (!selectedAttractions.some(a => a.id === attractionId)) {
            selectedAttractions.push(attraction);
            updateSelectedAttractionsList();

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
        if (!selectedAttractionsList) return;
        selectedAttractionsList.innerHTML = '';

        selectedAttractions.forEach(attraction => {
            const li = document.createElement('li');
            li.innerHTML = `
                <div class="attraction-item">
                    <h4>${attraction.name}</h4>
                    <p>${attraction.address}</p>
                    <button onclick="removeAttraction('${attraction.id}')">Remove</button>
                </div>
            `;
            selectedAttractionsList.appendChild(li);
        });
    }

    // Remove attraction from selection
    function removeAttraction(attractionId) {
        if (!map) return;
        const attraction = selectedAttractions.find(a => a.id === attractionId);
        if (!attraction) return;

        selectedAttractions = selectedAttractions.filter(a => a.id !== attractionId);
        updateSelectedAttractionsList();

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
});
