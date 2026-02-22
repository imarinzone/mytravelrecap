/**
 * Vercel Serverless Function – proxy for Google Places photo media.
 * Streams the photo binary so the API key never reaches the browser.
 *
 * GET /api/places/photo?ref=<photoResourceName>&maxWidth=400
 */
export default async function handler(req, res) {
    if (req.method !== 'GET') {
        res.setHeader('Allow', 'GET');
        return res.status(405).json({ error: 'Method not allowed' });
    }

    const apiKey = process.env.GOOGLE_PLACES_API_KEY || '';
    if (!apiKey) {
        return res.status(501).json({ error: 'Google Places API key not configured' });
    }

    const { ref, maxWidth } = req.query;
    if (!ref || typeof ref !== 'string') {
        return res.status(400).json({ error: 'ref query parameter is required' });
    }

    const width = parseInt(maxWidth, 10) || 400;

    try {
        const photoUrl = `https://places.googleapis.com/v1/${ref}/media?maxWidthPx=${width}&key=${encodeURIComponent(apiKey)}`;
        const photoRes = await fetch(photoUrl);

        if (!photoRes.ok) {
            console.error('Places photo fetch failed', photoRes.status);
            return res.status(photoRes.status).end();
        }

        // Forward content-type and cache aggressively (photos don't change)
        const contentType = photoRes.headers.get('content-type') || 'image/jpeg';
        res.setHeader('Content-Type', contentType);
        res.setHeader('Cache-Control', 'public, s-maxage=604800, max-age=86400, stale-while-revalidate=604800');

        // Stream the response body
        const buffer = Buffer.from(await photoRes.arrayBuffer());
        return res.status(200).send(buffer);
    } catch (err) {
        console.error('places/photo error', err);
        return res.status(500).json({ error: 'Internal server error' });
    }
}
