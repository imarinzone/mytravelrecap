#!/usr/bin/env node
/**
 * Injects environment variables into config.js at build time.
 *
 * NOTE: GOOGLE_PLACES_API_KEY is no longer injected here.
 * It is used exclusively server-side via Vercel Serverless Functions
 * (see /api/places/*.js). This script is kept for any future
 * client-side config values that may need build-time injection.
 */

// Currently no client-side env vars need injection.
// The build script in package.json still calls this so it exits cleanly.
console.log('inject-env: no client-side env vars to inject');
