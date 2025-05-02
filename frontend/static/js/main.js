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
        budget: null,
        ai_recommendation_generated: false,
        user_input_processed: false,
        session_id: null
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
        
        // Use marked to render Markdown content
        messageContent.innerHTML = marked.parse(message);
        
        messageDiv.appendChild(messageContent);
        chatContainer.appendChild(messageDiv);
        
        // Scroll to bottom
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }
    
    // Process user input by sending to backend
    function processUserInput(message) {
        // Show loading spinner
        loadingSpinner.classList.remove('d-none');
        
        // Create a new message container for the assistant's response
        const messageDiv = document.createElement('div');
        messageDiv.className = 'chat-message assistant';
        const messageContent = document.createElement('div');
        messageContent.className = 'message-content';
        messageDiv.appendChild(messageContent);
        chatContainer.appendChild(messageDiv);
        
        // Create EventSource for streaming
        const params = new URLSearchParams({
            step: state.step,
            user_input: message,
            session_id: state.session_id || ''
        });
        
        // Add selected attractions if in recommend step
        if (state.step === 'recommend' && state.selectedAttractions.length > 0) {
            params.append('selected_attraction_ids', JSON.stringify(state.selectedAttractions.map(a => a.id)));
        }
        
        // Add state flags if they exist
        if (state.ai_recommendation_generated !== undefined) {
            params.append('ai_recommendation_generated', state.ai_recommendation_generated.toString());
        }
        if (state.user_input_processed !== undefined) {
            params.append('user_input_processed', state.user_input_processed.toString());
        }
        
        console.log('[DEBUG] Sending request with params:', params.toString());
        console.log('[DEBUG] Current state:', state);
        
        const eventSource = new EventSource(`/api/stream?${params.toString()}`);
        
        let fullResponse = '';
        
        eventSource.onmessage = function(event) {
            const data = JSON.parse(event.data);
            console.log('[DEBUG] Received data:', data);
            
            if (data.type === 'chunk') {
                fullResponse += data.content;
                messageContent.innerHTML = marked.parse(fullResponse);
                chatContainer.scrollTop = chatContainer.scrollHeight;
            } else if (data.type === 'complete') {
                eventSource.close();
                loadingSpinner.classList.add('d-none');
            
                const prevStep = state.step;
                state.step = data.next_step || state.step;
                if (data.next_step) {
                    updateStepNav(data.next_step);
                }
                // 自动触发: 只有当上一步是 recommend，且新 step 是 strategy 时
                if (prevStep === 'recommend' && state.step === 'strategy') {
                    setTimeout(() => {
                        processUserInput('Here are my selected attractions');
                    }, 0);
                }
                // Store session_id if provided
                if (data.session_id) {
                    state.session_id = data.session_id;
                    console.log('[DEBUG] Updated session_id:', state.session_id);
                }
                // Display or hide missing fields
                if (data.missing_fields && data.missing_fields.length > 0) {
                    showMissingFields(data.missing_fields);
                } else {
                    hideMissingFields();
                }
                // Update state from response
                if (data.state) {
                    console.log('[DEBUG] Updating state with:', data.state);
                    if (data.state.user_info) state.userInfo = data.state.user_info;
                    if (data.state.attractions) state.attractions = data.state.attractions;
                    if (data.state.selected_attractions) state.selectedAttractions = data.state.selected_attractions;
                    if (data.state.itinerary) state.itinerary = data.state.itinerary;
                    if (data.state.budget) state.budget = data.state.budget;
                    if (data.state.ai_recommendation_generated !== undefined) {
                        state.ai_recommendation_generated = Boolean(data.state.ai_recommendation_generated);
                        console.log('[DEBUG] Updated ai_recommendation_generated:', state.ai_recommendation_generated);
                    }
                    if (data.state.user_input_processed !== undefined) {
                        state.user_input_processed = Boolean(data.state.user_input_processed);
                        console.log('[DEBUG] Updated user_input_processed:', state.user_input_processed);
                    }
                }
                // Update UI components
                if (data.attractions) updateAttractions(data.attractions);
                if (data.map_data) updateMap(data.map_data);
                if (data.itinerary) updateItinerary(data.itinerary);
                if (data.budget) updateBudget(data.budget);
                if (data.response) updateConfirmation(data.response);

                // 关键修改：如果进入 complete 阶段（即 route 阶段返回 next_step: 'complete'），直接渲染 itinerary 和 budget，不再发起新的请求
                if (state.step === 'complete') {
                    // 已经在本次响应中渲染 itinerary 和 budget，无需再发 step=complete 请求
                    // 可以在此处添加提示或高亮，表示行程已生成
                    addChatMessage('Your itinerary and budget have been generated! Check the left panel for details.', 'assistant');
                }

                // If we have route data, draw it on the map
                if (data.optimal_route) {
                    drawRoute(data.optimal_route);
                }

                console.log('[DEBUG] Final state:', state);
            } else if (data.type === 'error') {
                eventSource.close();
                loadingSpinner.classList.add('d-none');
                messageContent.innerHTML = 'Sorry, there was an error processing your request. Please try again.';
                console.error('Error:', data.error);
            }
        };
        
        eventSource.onerror = function(error) {
            console.error('EventSource failed:', error);
            eventSource.close();
            loadingSpinner.classList.add('d-none');
            messageContent.innerHTML = 'Sorry, there was an error processing your request. Please try again.';
        };
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
                    // 获取并显示周边信息，直接传入整个attraction对象
                    fetchNearbyPlaces(attraction);
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
        
        // Only add confirm button if we're not already in the strategy step
        if (state.step !== 'strategy') {
            // Add confirm button
            const confirmBtn = document.createElement('button');
            confirmBtn.className = 'btn btn-primary w-100';
            confirmBtn.textContent = 'Confirm Selection';
            confirmBtn.addEventListener('click', function() {
                if (state.selectedAttractions.length > 0) {
                    // Show processing message
                    // addChatMessage('Processing your selected attractions...', 'assistant');
                    
                    // Update selected attractions list
                    updateSelectedAttractionsList(state.selectedAttractions);
                    
                    // Process the selection
                    processUserInput('Here are my selected attractions');
                } else {
                    addChatMessage('Please select at least one attraction.', 'assistant');
                }
            });
            
            recommendationsContainer.appendChild(confirmBtn);
        }
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
        const budgetDiv = document.getElementById('budget-container');
        if (!budgetDiv || !budget) return;
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
    }
    
    // Update confirmation display
    function updateConfirmation(response) {
        const confirmationDiv = document.getElementById('confirmation-container');
        if (!confirmationDiv) return;
        confirmationDiv.innerHTML = '';
        if (!response) {
            confirmationDiv.innerHTML = '<p class="text-center text-muted">Trip confirmation and details will appear here once generated.</p>';
            return;
        }
        // 支持 markdown 格式
        confirmationDiv.innerHTML = `<div class="message-content">${marked.parse(response)}</div>`;
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
                    budget: null,
                    ai_recommendation_generated: false,
                    user_input_processed: false,
                    session_id: null
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
    function updateSelectedAttractionsList(attractions) {
        const selectedAttractionsList = document.getElementById('selected-attractions');
        if (!selectedAttractionsList) return;
        
        selectedAttractionsList.innerHTML = '';
        
        if (!attractions || attractions.length === 0) {
            selectedAttractionsList.innerHTML = '<p class="text-center text-muted">No attractions selected yet.</p>';
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
                    <h6 class="card-title mb-1">${attraction.name}</h6>
                    <p class="card-text mb-1">
                        <small class="text-muted">${attraction.category || 'attraction'}</small>
                        <small class="ms-2">${priceLevel}</small>
                        <small class="ms-2">${rating}</small>
                    </p>
                    <small class="text-muted">${attraction.estimated_duration || 2} hours</small>
                </div>
            `;
            
            selectedAttractionsList.appendChild(card);
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

    // Add new function to draw route on map
    function drawRoute(route) {
        if (!map || !route || route.length < 2) return;
        
        // Clear any existing route
        if (window.routeLayer) {
            map.removeLayer(window.routeLayer);
        }
        
        // Create a new layer for the route
        window.routeLayer = L.layerGroup().addTo(map);
        
        // Create a polyline connecting all points
        const points = route.map(spot => [spot.location.lat, spot.location.lng]);
        const polyline = L.polyline(points, {
            color: '#007bff',
            weight: 4,
            opacity: 0.7,
            smoothFactor: 1
        }).addTo(window.routeLayer);
        
        // Add markers for each point with numbers
        route.forEach((spot, index) => {
            const marker = L.marker([spot.location.lat, spot.location.lng], {
                icon: L.divIcon({
                    className: 'route-marker',
                    html: `<div class="route-marker-number">${index + 1}</div>`,
                    iconSize: [24, 24]
                })
            }).addTo(window.routeLayer);
            
            marker.bindPopup(`
                <h3>${spot.name || 'Unknown'}</h3>
                <p>Stop ${index + 1}</p>
            `);
        });
        
        // Fit bounds to show the entire route
        map.fitBounds(polyline.getBounds().pad(0.1));
    }

    // Modify fetchNearbyPlaces function
    function fetchNearbyPlaces(attraction) {
        // Use latitude and longitude instead of name
        const coordinates = `${attraction.location.lat},${attraction.location.lng}`;
        fetch(`/api/nearby/${coordinates}`)
            .then(response => response.json())
            .then(data => {
                // Display nearby information in the chat box
                const nearbyMessage = formatNearbyPlacesMessage(data);
                addChatMessage(nearbyMessage, 'assistant');
            })
            .catch(error => {
                console.error('Error fetching nearby places:', error);
                addChatMessage('Sorry, there was an error fetching nearby places. Please try again later.', 'assistant');
            });
    }

    // Format nearby information message
    function formatNearbyPlacesMessage(data) {
        let message = '### Nearby Recommendations\n\n';

        // Nearby Restaurants
        if (data.restaurants && data.restaurants.length > 0) {
            message += '#### 🍽️ Nearby Restaurants\n';
            data.restaurants.forEach(restaurant => {
                message += `<div class=\"nearby-item\" style=\"margin-bottom:18px;\">`;
                if (restaurant.photos && restaurant.photos.length > 0) {
                    message += `<img src=\"${restaurant.photos[0].url}\" style=\"max-width:180px; border-radius:8px; display:block; margin-bottom:6px;\" />`;
                }
                message += `<div style=\"font-weight:bold; margin-bottom:2px;\">${restaurant.name}</div>`;
                message += `<div style=\"font-size:13px; color:#555;\">Type: ${restaurant.type} | Rating: ${restaurant.rating}⭐</div>`;
                message += `<div style=\"font-size:13px; color:#555;\">Price: ${'💰'.repeat(restaurant.price_level)} | Address: ${restaurant.address}</div>`;
                message += `</div>`;
            });
        }

        return message;
    }

    // Make functions available globally
    window.updateMap = updateMap;
    window.selectAttraction = selectAttraction;
    window.removeAttraction = removeAttraction;
});
