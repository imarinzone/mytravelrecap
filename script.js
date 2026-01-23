// Leaflet Map Configuration
let map = null;
let markers = null;
let currentStyle = 'light';
let selectedYear = null;
let allLocations = []; // Store loaded locations for filtering

// CartoDB Tile Layer URLs

// CartoDB Tile Layer URLs
const tileLayers = {
    light: L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
        attribution: '© OpenStreetMap contributors © CARTO',
        subdomains: 'abcd',
        maxZoom: 19
    }),
    dark: L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
        attribution: '© OpenStreetMap contributors © CARTO',
        subdomains: 'abcd',
        maxZoom: 19
    })
};

// Initialize map
function initMap() {
    // Load saved style preference
    const savedStyle = localStorage.getItem('mapStyle');
    if (savedStyle === 'dark' || savedStyle === 'light') {
        currentStyle = savedStyle;
    }

    // Create map with default center (will be adjusted based on data bounds)
    map = L.map('map', {
        center: [20, 0],
        zoom: 2,
        zoomControl: true
    });

    // Add initial tile layer
    tileLayers[currentStyle].addTo(map);
    updateStyleButtons();
    updateMapTheme();

    // Initialize marker layer (using LayerGroup instead of clustering to show individual points)
    markers = L.layerGroup();
    map.addLayer(markers);

    // Initialize year dropdown
    initializeYearFilter();

    // Load saved year preference
    const savedYear = localStorage.getItem('mapYear');
    if (savedYear) {
        document.getElementById('map-year-filter').value = savedYear;
        selectedYear = savedYear === '' ? null : savedYear;
    }

    // Setup fullscreen listeners
    setupFullscreenListeners();

    // Load place locations
    loadPlaceLocations();
}

// Initialize year filter dropdown
function initializeYearFilter() {
    const yearSelect = document.getElementById('map-year-filter');
    const currentYear = new Date().getFullYear();
    const startYear = 2020; // Adjust as needed

    // Generate year options (from startYear to currentYear, descending)
    for (let year = currentYear; year >= startYear; year--) {
        const option = document.createElement('option');
        option.value = year;
        option.textContent = year;
        yearSelect.appendChild(option);
    }
}

// Render markers based on current data and filters
function renderMarkers() {
    // Clear existing markers
    markers.clearLayers();

    if (allLocations.length === 0) {
        return;
    }

    let filteredLocations = allLocations;

    // Apply year filter if selected
    if (selectedYear) {
        const yearInt = parseInt(selectedYear);
        filteredLocations = allLocations.filter(loc => {
            if (!loc.startTime) return false;
            const visitYear = new Date(loc.startTime).getFullYear();
            return visitYear === yearInt;
        });
    }

    if (filteredLocations.length === 0) {
        console.warn('No locations found for selected year');
        return;
    }

    // Calculate bounds
    const bounds = L.latLngBounds([]);
    filteredLocations.forEach(loc => {
        bounds.extend([loc.lat, loc.lng]);
    });

    // Fit map to bounds
    map.fitBounds(bounds, { padding: [50, 50] });

    // Add markers as individual points
    filteredLocations.forEach(loc => {
        const popupContent = buildPopupContent(loc);
        // Create a custom icon for a simple red point
        const pointIcon = L.divIcon({
            className: 'custom-point-marker',
            html: '<div style="width: 8px; height: 8px; background-color: #ef4444; border: 2px solid white; border-radius: 50%; box-shadow: 0 2px 4px rgba(0,0,0,0.3);"></div>',
            iconSize: [8, 8],
            iconAnchor: [4, 4]
        });
        const marker = L.marker([loc.lat, loc.lng], { icon: pointIcon })
            .bindPopup(popupContent);
        markers.addLayer(marker);
    });

    console.log(`Rendered ${filteredLocations.length} markers`);
}

// Handle file upload
function handleFileUpload(event) {
    const file = event.target.files[0];
    if (!file) {
        return;
    }

    const statusSpan = document.getElementById('upload-status');
    statusSpan.textContent = 'Parsing...';

    const reader = new FileReader();
    reader.onload = function (e) {
        try {
            const json = JSON.parse(e.target.result);
            processTimelineData(json);
            statusSpan.textContent = `Loaded ${allLocations.length} visits`;
            statusSpan.className = 'text-sm font-medium text-green-600';
        } catch (error) {
            console.error('Error parsing JSON:', error);
            statusSpan.textContent = 'Error parsing JSON file';
            statusSpan.className = 'text-sm font-medium text-red-600';
        }
    };
    reader.readAsText(file);
}

// Process Google Timeline JSON
function processTimelineData(data) {
    allLocations = [];
    const segments = data.semanticSegments || [];

    segments.forEach(segment => {
        if (segment.visit) {
            const visit = segment.visit;
            if (visit.topCandidate && visit.topCandidate.placeLocation && visit.topCandidate.placeLocation.latLng) {
                const latLngStr = visit.topCandidate.placeLocation.latLng;
                // Parse "lat°, lng°" format
                const parts = latLngStr.replace(/°/g, '').split(',');
                if (parts.length === 2) {
                    const lat = parseFloat(parts[0].trim());
                    const lng = parseFloat(parts[1].trim());

                    if (!isNaN(lat) && !isNaN(lng)) {
                        allLocations.push({
                            lat: lat,
                            lng: lng,
                            startTime: segment.startTime, // Keep start time for filtering
                            // metadata we can extract
                            address: visit.topCandidate.placeLocation.address,
                            name: visit.topCandidate.placeLocation.name,
                            probability: visit.probability
                        });
                    }
                }
            }
        }
    });

    console.log(`Parsed ${allLocations.length} locations`);
    renderMarkers();
    initializeYearFilter(); // Re-initialize years based on data if we wanted to be dynamic, but static is fine for now
}

// Load place locations - REPLACED BY FILE UPLOAD
function loadPlaceLocations() {
    // Initial load does nothing now, waiting for file upload
    const mapDiv = document.getElementById('map');
    // Optional: Add a "Waiting for data" overlay or similar if needed
}

// Build popup content for marker
function buildPopupContent(location) {
    let content = '<div class="text-sm">';

    if (location.name) {
        content += `<strong>${location.name}</strong><br>`;
    }

    if (location.address) {
        content += `<span class="text-xs text-gray-600">${location.address}</span><br>`;
    } else {
        content += `<strong>Unknown Location</strong><br>`;
    }

    if (location.startTime) {
        const date = new Date(location.startTime);
        content += `<span class="text-xs text-gray-500">${date.toLocaleDateString()}</span><br>`;
    }

    content += `<span class="text-xs text-gray-400">${location.lat.toFixed(4)}, ${location.lng.toFixed(4)}</span>`;
    content += '</div>';
    return content;
}

// Switch map style
function switchMapStyle(style) {
    if (style === currentStyle) return;

    currentStyle = style;
    localStorage.setItem('mapStyle', style);

    // Remove current layer
    map.eachLayer(layer => {
        if (layer instanceof L.TileLayer) {
            map.removeLayer(layer);
        }
    });

    // Add new layer
    tileLayers[currentStyle].addTo(map);
    updateStyleButtons();
    updateMapTheme();
}

// Apply dark theme filter when using dark style
function updateMapTheme() {
    const mapDiv = document.getElementById('map');
    if (!mapDiv) return;

    if (currentStyle === 'dark') {
        mapDiv.classList.add('map-dark');
    } else {
        mapDiv.classList.remove('map-dark');
    }
}

// Update style button states
function updateStyleButtons() {
    const lightBtn = document.getElementById('map-style-light');
    const darkBtn = document.getElementById('map-style-dark');

    if (currentStyle === 'light') {
        lightBtn.classList.remove('bg-gray-200', 'text-gray-700', 'hover:bg-gray-300');
        lightBtn.classList.add('bg-blue-600', 'text-white', 'hover:bg-blue-700');
        darkBtn.classList.remove('bg-blue-600', 'text-white', 'hover:bg-blue-700');
        darkBtn.classList.add('bg-gray-200', 'text-gray-700', 'hover:bg-gray-300');
    } else {
        darkBtn.classList.remove('bg-gray-200', 'text-gray-700', 'hover:bg-gray-300');
        darkBtn.classList.add('bg-blue-600', 'text-white', 'hover:bg-blue-700');
        lightBtn.classList.remove('bg-blue-600', 'text-white', 'hover:bg-blue-700');
        lightBtn.classList.add('bg-gray-200', 'text-gray-700', 'hover:bg-gray-300');
    }
}

// Handle year filter change
function onYearFilterChange() {
    const yearSelect = document.getElementById('map-year-filter');
    selectedYear = yearSelect.value === '' ? null : yearSelect.value;
    localStorage.setItem('mapYear', yearSelect.value);
    renderMarkers();
}

// Toggle fullscreen
function toggleFullscreen() {
    const mapSection = document.querySelector('#map-container-wrapper').closest('section');

    if (!document.fullscreenElement && !document.webkitFullscreenElement && !document.msFullscreenElement) {
        // Enter fullscreen
        if (mapSection.requestFullscreen) {
            mapSection.requestFullscreen();
        } else if (mapSection.webkitRequestFullscreen) {
            mapSection.webkitRequestFullscreen();
        } else if (mapSection.webkitRequestFullscreen) {
            mapSection.webkitRequestFullscreen(Element.ALLOW_KEYBOARD_INPUT);
        } else if (mapSection.msRequestFullscreen) {
            mapSection.msRequestFullscreen();
        }
    } else {
        // Exit fullscreen
        if (document.exitFullscreen) {
            document.exitFullscreen();
        } else if (document.webkitExitFullscreen) {
            document.webkitExitFullscreen();
        } else if (document.msExitFullscreen) {
            document.msExitFullscreen();
        }
    }
}

// Handle fullscreen change
function handleFullscreenChange() {
    const isFullscreen = !!(document.fullscreenElement || document.webkitFullscreenElement || document.msFullscreenElement);
    const fullscreenIcon = document.getElementById('fullscreen-icon');
    const fullscreenText = document.getElementById('fullscreen-text');
    const fullscreenBtn = document.getElementById('map-fullscreen');

    if (isFullscreen) {
        fullscreenIcon.textContent = '⛶';
        if (fullscreenText) fullscreenText.textContent = 'Exit';
        fullscreenBtn.setAttribute('title', 'Exit fullscreen');
        // Resize map after entering fullscreen
        setTimeout(() => {
            map.invalidateSize();
        }, 100);
    } else {
        fullscreenIcon.textContent = '⛶';
        if (fullscreenText) fullscreenText.textContent = 'Fullscreen';
        fullscreenBtn.setAttribute('title', 'Toggle fullscreen');
        // Resize map after exiting fullscreen
        setTimeout(() => {
            map.invalidateSize();
        }, 100);
    }
}

// Setup fullscreen event listeners
function setupFullscreenListeners() {
    document.addEventListener('fullscreenchange', handleFullscreenChange);
    document.addEventListener('webkitfullscreenchange', handleFullscreenChange);
    document.addEventListener('msfullscreenchange', handleFullscreenChange);
}

// Initialize map when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        initMap();
        // Style switcher event listeners
        document.getElementById('map-style-light').addEventListener('click', () => switchMapStyle('light'));
        document.getElementById('map-style-dark').addEventListener('click', () => switchMapStyle('dark'));
        // Year filter event listener
        document.getElementById('map-year-filter').addEventListener('change', onYearFilterChange);
        // Fullscreen event listener
        document.getElementById('map-fullscreen').addEventListener('click', toggleFullscreen);

        // File input listener
        const fileInput = document.getElementById('timeline-file-input');
        if (fileInput) {
            fileInput.addEventListener('change', handleFileUpload);
        }
    });
} else {
    initMap();
    // Style switcher event listeners
    document.getElementById('map-style-light').addEventListener('click', () => switchMapStyle('light'));
    document.getElementById('map-style-dark').addEventListener('click', () => switchMapStyle('dark'));
    // Year filter event listener
    document.getElementById('map-year-filter').addEventListener('change', onYearFilterChange);
    // Fullscreen event listener
    document.getElementById('map-fullscreen').addEventListener('click', toggleFullscreen);

    // File input listener
    const fileInput = document.getElementById('timeline-file-input');
    if (fileInput) {
        fileInput.addEventListener('change', handleFileUpload);
    }
}

