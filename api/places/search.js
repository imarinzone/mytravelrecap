/**
 * Vercel Serverless Function – proxy for Google Places searchNearby.
 * Keeps the API key server-side; the browser never sees it.
 *
 * POST /api/places/search
 * Body: { lat: number, lng: number, radius?: number }
 * Returns: { displayName, formattedAddress, photoRef } or { error }
 */
export default async function handler(req, res) {
    // Only allow POST
    if (req.method !== 'POST') {
        res.setHeader('Allow', 'POST');
        return res.status(405).json({ error: 'Method not allowed' });
    }

    const apiKey = process.env.GOOGLE_PLACES_API_KEY || '';
    if (!apiKey) {
        return res.status(501).json({ error: 'Google Places API key not configured' });
    }

    const { lat, lng, radius } = req.body || {};
    if (typeof lat !== 'number' || typeof lng !== 'number') {
        return res.status(400).json({ error: 'lat and lng are required numbers' });
    }

    try {
        const searchUrl = 'https://places.googleapis.com/v1/places:searchNearby';
        const searchBody = JSON.stringify({
            maxResultCount: 1,
            rankPreference: 'DISTANCE',
            locationRestriction: {
                circle: {
                    center: { latitude: lat, longitude: lng },
                    radius: radius || 50
                }
            }
        });

        const searchRes = await fetch(searchUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Goog-Api-Key': apiKey,
                'X-Goog-FieldMask': 'places.id,places.displayName,places.formattedAddress,places.photos'
            },
            body: searchBody
        });

        if (!searchRes.ok) {
            const errText = await searchRes.text();
            console.error('Places searchNearby failed', searchRes.status, errText);
            return res.status(searchRes.status).json({ error: 'Places API error', detail: errText });
        }

        const searchData = await searchRes.json();
        const places = searchData.places;
        if (!places || places.length === 0) {
            return res.status(200).json(null);
        }

        const place = places[0];
        const displayName = place.displayName && place.displayName.text ? place.displayName.text : null;
        const formattedAddress = place.formattedAddress || null;

        // Return the photo resource name (not the full URL with key).
        // The frontend will use /api/places/photo?ref=<name> to fetch it.
        let photoRef = null;
        if (place.photos && place.photos.length > 0 && place.photos[0].name) {
            photoRef = place.photos[0].name;
        }

        // Cache for 1 hour on Vercel edge
        res.setHeader('Cache-Control', 's-maxage=3600, stale-while-revalidate=86400');
        return res.status(200).json({ displayName, formattedAddress, photoRef });
    } catch (err) {
        console.error('places/search error', err);
        return res.status(500).json({ error: 'Internal server error' });
    }
}
