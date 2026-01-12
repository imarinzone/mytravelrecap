// Leaflet Map Configuration
let map = null;
let markers = null;
let currentStyle = 'light';

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

    // Initialize marker cluster group
    markers = L.markerClusterGroup({
        maxClusterRadius: 50,
        spiderfyOnMaxZoom: true,
        showCoverageOnHover: false,
        zoomToBoundsOnClick: true
    });
    map.addLayer(markers);

    // Load place locations
    loadPlaceLocations();
}

// Load place locations from API
async function loadPlaceLocations() {
    try {
        const response = await fetch('http://localhost:8080/api/place-locations');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const locations = await response.json();

        if (locations.length === 0) {
            console.warn('No place locations found');
            return;
        }

        // Calculate bounds
        const bounds = L.latLngBounds([]);
        locations.forEach(loc => {
            bounds.extend([loc.lat, loc.lng]);
        });

        // Fit map to bounds
        map.fitBounds(bounds, { padding: [50, 50] });

        // Add markers
        locations.forEach(loc => {
            const popupContent = buildPopupContent(loc);
            const marker = L.marker([loc.lat, loc.lng])
                .bindPopup(popupContent);
            markers.addLayer(marker);
        });

        console.log(`Loaded ${locations.length} place locations`);
    } catch (error) {
        console.error('Error loading place locations:', error);
        // Show error message in map container
        const mapDiv = document.getElementById('map');
        mapDiv.innerHTML = `
            <div class="flex items-center justify-center h-full bg-gray-100">
                <div class="text-center p-4">
                    <p class="text-gray-600 mb-2">Unable to load map data</p>
                    <p class="text-sm text-gray-500">Please ensure the backend API is running</p>
                </div>
            </div>
        `;
    }
}

// Build popup content for marker
function buildPopupContent(location) {
    let content = '<div class="text-sm">';
    if (location.city) {
        content += `<strong>${location.city}</strong>`;
    }
    if (location.country) {
        if (location.city) {
            content += `, ${location.country}`;
        } else {
            content += `<strong>${location.country}</strong>`;
        }
    }
    content += `<br><span class="text-gray-500">${location.lat.toFixed(4)}, ${location.lng.toFixed(4)}</span>`;
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

// Initialize map when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        initMap();
        // Style switcher event listeners
        document.getElementById('map-style-light').addEventListener('click', () => switchMapStyle('light'));
        document.getElementById('map-style-dark').addEventListener('click', () => switchMapStyle('dark'));
    });
} else {
    initMap();
    // Style switcher event listeners
    document.getElementById('map-style-light').addEventListener('click', () => switchMapStyle('light'));
    document.getElementById('map-style-dark').addEventListener('click', () => switchMapStyle('dark'));
}

