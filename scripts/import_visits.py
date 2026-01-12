#!/usr/bin/env python
"""
Import visit data from GoogleTimeline.json into Postgres database.

Extracts segments with "visit" field and stores:
- start_time (from segment.startTime)
- lat, lng (parsed from visit.topCandidate.placeLocation.latLng)
- probability (from visit.probability)
- place_id (from visit.topCandidate.placeId, optional)
"""

import json
import logging
import os
import re
import sys
import time
from datetime import datetime
from typing import Dict, Optional, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

try:
    import psycopg2
    from psycopg2.extras import execute_batch
except ImportError:
    print("Error: psycopg2 is required. Install it with: pip install psycopg2-binary")
    sys.exit(1)

try:
    from geopy.geocoders import Nominatim
    from geopy.exc import GeocoderServiceError, GeocoderTimedOut, GeocoderUnavailable
except ImportError:
    Nominatim = None  # type: ignore
    GeocoderServiceError = Exception  # type: ignore
    GeocoderTimedOut = Exception  # type: ignore
    GeocoderUnavailable = Exception  # type: ignore


def parse_lat_lng(lat_lng_str: str) -> Optional[Tuple[float, float]]:
    """
    Parse latitude and longitude from string format like "13.0378414°, 77.5758153°"
    
    Args:
        lat_lng_str: String in format "lat°, lng°"
        
    Returns:
        Tuple of (lat, lng) as floats, or None if parsing fails
    """
    if not lat_lng_str:
        return None
    
    # Remove degree symbols and whitespace, then split by comma
    cleaned = lat_lng_str.replace('°', '').strip()
    parts = cleaned.split(',')
    
    if len(parts) != 2:
        return None
    
    try:
        lat = float(parts[0].strip())
        lng = float(parts[1].strip())
        return (lat, lng)
    except (ValueError, AttributeError):
        return None


def get_db_connection():
    """Create Postgres connection using environment variables."""
    host = os.getenv('DB_HOST', 'localhost')
    port = os.getenv('DB_PORT', '5432')
    user = os.getenv('DB_USER', 'travelrecap')
    password = os.getenv('DB_PASSWORD', 'travelrecap_password')
    dbname = os.getenv('DB_NAME', 'travelrecap')
    
    logger.info(f"Connecting to database: {dbname}@{host}:{port} as {user}")
    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            dbname=dbname
        )
        logger.info("✓ Database connection established")
        return conn
    except psycopg2.Error as e:
        logger.error(f"Error connecting to database: {e}")
        sys.exit(1)


def extract_visit_data(segment: dict) -> Optional[dict]:
    """
    Extract visit data from a segment if it contains a visit field.
    
    Returns:
        Dictionary with visit data or None if not a visit segment or data is invalid
    """
    if 'visit' not in segment:
        return None
    
    visit = segment.get('visit', {})
    top_candidate = visit.get('topCandidate', {})
    place_location = top_candidate.get('placeLocation', {})
    lat_lng_str = place_location.get('latLng')
    
    # Parse lat/lng
    lat_lng = parse_lat_lng(lat_lng_str) if lat_lng_str else None
    if lat_lng is None:
        return None  # Skip if we can't parse coordinates
    
    lat, lng = lat_lng
    
    # Extract required fields
    start_time = segment.get('startTime')
    if not start_time:
        return None
    
    probability = visit.get('probability')
    if probability is None:
        return None
    
    place_id = top_candidate.get('placeId')
    
    return {
        'start_time': start_time,
        'lat': lat,
        'lng': lng,
        'probability': probability,
        'place_id': place_id
    }


class Geocoder:
    """Nominatim-based reverse geocoder with database caching by place_id and in-memory cache."""

    def __init__(self, conn=None, timeout=10, max_retries=2):
        self.conn = conn
        self.enabled = Nominatim is not None
        self.timeout = timeout
        self.max_retries = max_retries
        if not self.enabled:
            print("Warning: geopy is not installed; geocoding will be disabled.")
            self.geolocator = None
        else:
            # user_agent is required by Nominatim usage policy
            # timeout: seconds to wait for response before giving up
            self.geolocator = Nominatim(
                user_agent="travelrecap-visit-importer",
                timeout=timeout
            )
        # In-memory cache keyed by (rounded_lat, rounded_lng) for coordinates without place_id
        self._cache: Dict[Tuple[float, float], Dict[str, Optional[str]]] = {}
        # In-memory cache keyed by place_id
        self._place_cache: Dict[str, Dict[str, Optional[str]]] = {}
        self._last_call_ts: Optional[float] = None

    def get_place_location(self, place_id: Optional[str]) -> Optional[Dict[str, Optional[str]]]:
        """
        Get cached location data for a place_id from database or in-memory cache.
        
        Checks in this order:
        1. In-memory cache (fastest)
        2. Database table place_locations (fast)
        3. Returns None if not found (will need API call)
        """
        if not place_id or not self.conn:
            return None
        
        # Step 1: Check in-memory cache first (fastest)
        if place_id in self._place_cache:
            logger.debug(f"✓ Found place_id {place_id} in memory cache")
            return self._place_cache[place_id]
        
        # Step 2: Check database table
        logger.debug(f"Checking database for place_id {place_id}...")
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT lat, lng, city, state, country, address, geocoded_at
                    FROM place_locations
                    WHERE place_id = %s
                """, (place_id,))
                row = cur.fetchone()
                if row:
                    result = {
                        "lat": row[0],
                        "lng": row[1],
                        "city": row[2],
                        "state": row[3],
                        "country": row[4],
                        "address": row[5],
                        "geocoded_at": row[6].isoformat() if row[6] else None,
                    }
                    # Store in memory cache for future lookups
                    self._place_cache[place_id] = result
                    logger.debug(f"✓ Found place_id {place_id} in database: {result.get('city')}, {result.get('country')}")
                    return result
                else:
                    logger.debug(f"✗ place_id {place_id} not found in database - will need API call")
        except psycopg2.Error as e:
            logger.warning(f"Error querying place_locations for {place_id}: {e}")
        
        return None

    def save_place_location(self, place_id: Optional[str], lat: float, lng: float,
                           location_data: Dict[str, Optional[str]]):
        """Save geocoded location data to place_locations table."""
        if not place_id or not self.conn:
            return
        
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO place_locations (
                        place_id, lat, lng, city, state, country, address, geocoded_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (place_id) 
                    DO UPDATE SET
                        lat = EXCLUDED.lat,
                        lng = EXCLUDED.lng,
                        city = EXCLUDED.city,
                        state = EXCLUDED.state,
                        country = EXCLUDED.country,
                        address = EXCLUDED.address,
                        geocoded_at = EXCLUDED.geocoded_at,
                        updated_at = NOW()
                """, (
                    place_id,
                    lat,
                    lng,
                    location_data.get("city"),
                    location_data.get("state"),
                    location_data.get("country"),
                    location_data.get("address"),
                ))
            self.conn.commit()
            # Also cache in memory
            self._place_cache[place_id] = {
                "lat": lat,
                "lng": lng,
                **location_data
            }
            logger.debug(f"Saved place_id {place_id} to cache: {location_data.get('city')}, {location_data.get('country')}")
        except psycopg2.Error as e:
            logger.error(f"Error saving place location for {place_id}: {e}")
            self.conn.rollback()

    def save_place_location_minimal(self, place_id: Optional[str], lat: float, lng: float):
        """
        Save minimal place_locations record (lat/lng only) to satisfy foreign key constraint.
        Used when geocoding fails or returns no results but we still have a place_id.
        """
        if not place_id or not self.conn:
            return
        
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO place_locations (
                        place_id, lat, lng, city, state, country, address, geocoded_at
                    )
                    VALUES (%s, %s, %s, NULL, NULL, NULL, NULL, NOW())
                    ON CONFLICT (place_id) 
                    DO UPDATE SET
                        lat = EXCLUDED.lat,
                        lng = EXCLUDED.lng,
                        updated_at = NOW()
                """, (place_id, lat, lng))
            self.conn.commit()
            # Also cache in memory (minimal record)
            self._place_cache[place_id] = {
                "lat": lat,
                "lng": lng,
                "city": None,
                "state": None,
                "country": None,
                "address": None,
            }
            logger.debug(f"Saved minimal place_id {place_id} (lat/lng only)")
        except psycopg2.Error as e:
            logger.error(f"Error saving minimal place location for {place_id}: {e}")
            self.conn.rollback()

    def reverse_geocode(self, lat: float, lng: float, place_id: Optional[str] = None) -> Dict[str, Optional[str]]:
        """
        Return dict with city, state, country, address; never raises.
        
        Checks in this order:
        1. place_locations table by place_id (if provided) - checks DB first
        2. In-memory coordinate cache
        3. Nominatim API (if not found in cache)
        """
        result: Dict[str, Optional[str]] = {
            "city": None,
            "state": None,
            "country": None,
            "address": None,
        }

        # Step 1: First, try to get from place_locations table by place_id (checks DB first)
        if place_id:
            cached = self.get_place_location(place_id)
            if cached:
                logger.debug(f"Using cached location for place_id {place_id} (from DB)")
                return {
                    "city": cached.get("city"),
                    "state": cached.get("state"),
                    "country": cached.get("country"),
                    "address": cached.get("address"),
                }

        if not self.enabled or self.geolocator is None:
            return result

        # Step 2: Check in-memory coordinate cache (for coordinates without place_id)
        key = (round(lat, 5), round(lng, 5))
        if key in self._cache:
            result = self._cache[key]
            logger.debug(f"Using cached location for coordinates ({lat}, {lng}) from memory")
            # Save to place_locations if we have a place_id (for future lookups)
            if place_id and any(result.values()):
                self.save_place_location(place_id, lat, lng, result)
            return result

        # Step 3: Not found in cache - need to call API
        logger.info(f"Calling Nominatim API for ({lat}, {lng}) - not found in cache")
        
        # Retry logic with exponential backoff for transient failures
        for attempt in range(self.max_retries + 1):
            # Basic rate limiting: 1 request/second (or longer after timeout)
            now = time.time()
            if self._last_call_ts is not None:
                elapsed = now - self._last_call_ts
                # Wait longer after timeout errors (3 seconds) vs normal rate limit (1 second)
                wait_time = 3.0 if attempt > 0 else 1.0
                if elapsed < wait_time:
                    time.sleep(wait_time - elapsed)

            try:
                logger.debug(f"Calling Nominatim API for ({lat}, {lng})...")
                api_start = time.time()
                location = self.geolocator.reverse((lat, lng), language="en")
                api_time = time.time() - api_start
                self._last_call_ts = time.time()
                
                if not location:
                    logger.debug(f"No location found for ({lat}, {lng}) in {api_time:.2f}s")
                    self._cache[key] = result
                    return result

                address = location.raw.get("address", {}) if hasattr(location, "raw") else {}
                city = (
                    address.get("city")
                    or address.get("town")
                    or address.get("village")
                    or address.get("hamlet")
                )
                state = address.get("state")
                country = address.get("country")

                result = {
                    "city": city,
                    "state": state,
                    "country": country,
                    "address": location.address if hasattr(location, "address") else None,
                }
                self._cache[key] = result
                
                logger.debug(f"Geocoded ({lat}, {lng}) -> {city}, {country} in {api_time:.2f}s")
                
                # Save to place_locations table if we have a place_id
                if place_id and any(result.values()):
                    self.save_place_location(place_id, lat, lng, result)
                    logger.debug(f"Saved place_id {place_id} to place_locations")
                
                return result
                
            except (GeocoderTimedOut, GeocoderUnavailable) as e:
                # Transient errors - retry with exponential backoff
                if attempt < self.max_retries:
                    wait = (2 ** attempt) * 2  # 2s, 4s, 8s...
                    logger.warning(f"Geocoding timeout/unavailable for ({lat}, {lng}), retrying in {wait}s (attempt {attempt + 1}/{self.max_retries + 1})...")
                    time.sleep(wait)
                    continue
                else:
                    logger.error(f"Geocoding failed after {self.max_retries + 1} attempts for ({lat}, {lng}): {e}")
                    self._last_call_ts = time.time()  # Update timestamp even on failure
                    
            except GeocoderServiceError as e:
                # Non-retryable service errors
                logger.error(f"Geocoding service error for ({lat}, {lng}): {e}")
                self._last_call_ts = time.time()
                break
                
            except Exception as e:  # Catch-all to avoid breaking import
                logger.error(f"Unexpected geocoding error for ({lat}, {lng}): {e}")
                self._last_call_ts = time.time()
                break

        # Cache the failure result to avoid retrying the same coordinates
        self._cache[key] = result
        return result


def import_visits(json_file_path: str, dry_run: bool = False, skip_geocode: bool = False):
    """
    Import visit data from GoogleTimeline.json into Postgres.
    
    Args:
        json_file_path: Path to GoogleTimeline.json file
        dry_run: If True, only print what would be imported without inserting
    """
    logger.info("=" * 60)
    logger.info("Starting visit import process")
    logger.info("=" * 60)
    logger.info(f"JSON file: {json_file_path}")
    logger.info(f"Dry run: {dry_run}")
    logger.info(f"Skip geocoding: {skip_geocode}")
    
    logger.info(f"Loading {json_file_path}...")
    start_time = time.time()
    
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        load_time = time.time() - start_time
        logger.info(f"✓ JSON loaded in {load_time:.2f} seconds")
    except FileNotFoundError:
        logger.error(f"File not found: {json_file_path}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in file: {e}")
        sys.exit(1)
    
    segments = data.get('semanticSegments', [])
    logger.info(f"Found {len(segments):,} total segments")
    
    # Extract visit data
    visits = []
    skipped = 0
    
    for i, segment in enumerate(segments):
        visit_data = extract_visit_data(segment)
        if visit_data:
            visits.append(visit_data)
        else:
            skipped += 1

        # Progress indicator for large files
        if (i + 1) % 10000 == 0:
            logger.info(f"  Processed {i + 1:,} segments, found {len(visits):,} visits...")
    
    extract_time = time.time() - start_time
    logger.info(f"✓ Extracted {len(visits):,} visits from {len(segments):,} segments in {extract_time:.2f} seconds")
    logger.info(f"  Skipped {skipped:,} non-visit segments ({skipped/len(segments)*100:.1f}%)")

    # Connect to database early if we need geocoding (to check place_locations cache)
    conn = None
    geocoder = None
    if not skip_geocode:
        if not dry_run:
            logger.info("Connecting to database for geocoding cache...")
            conn = get_db_connection()
            # Tables should already exist from schema.sql (Docker init)
            # Verify tables exist
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM place_locations")
                    cached_count = cur.fetchone()[0]
                    logger.info(f"Found {cached_count:,} cached places in place_locations table")
            except psycopg2.Error as e:
                logger.warning(f"Could not query place_locations table: {e}")
        else:
            # For dry-run, connect to show location info from cache
            logger.info("Connecting to database to show cached location info...")
            conn = get_db_connection()

    # Optionally geocode in batches
    geocoded_count = 0
    geocoded_from_cache = 0
    geocoded_from_api = 0
    geocode_errors = 0
    batch_size = 100  # Process visits in batches
    
    if not skip_geocode:
        if Nominatim is None:
            logger.warning("geopy/Nominatim not available, skipping geocoding.")
        else:
            if not dry_run:
                logger.info("Starting reverse geocoding (checking place_locations cache first)...")
                logger.info(f"Processing in batches of {batch_size} visits")
            geocode_start = time.time()
            geocoder = Geocoder(conn=conn, timeout=10, max_retries=2)
            if not dry_run:
                logger.info(f"Geocoder initialized with timeout=10s, max_retries=2")
            
            total_batches = (len(visits) + batch_size - 1) // batch_size
            logger.info(f"Total batches to process: {total_batches:,}")
            
            for batch_num in range(total_batches):
                batch_start_idx = batch_num * batch_size
                batch_end_idx = min((batch_num + 1) * batch_size, len(visits))
                batch_visits = visits[batch_start_idx:batch_end_idx]
                batch_start_time = time.time()
                
                batch_cached = 0
                batch_geocoded = 0
                batch_errors = 0
                
                logger.info(f"\n--- Batch {batch_num + 1}/{total_batches} ({len(batch_visits)} visits) ---")
                
                for idx, visit in enumerate(batch_visits):
                    global_idx = batch_start_idx + idx
                    place_id = visit.get("place_id")
                    
                    # Check if we already have this place_id in cache
                    cached = geocoder.get_place_location(place_id) if place_id else None
                    
                    if cached:
                        # Use cached data (already in place_locations table)
                        batch_cached += 1
                        geocoded_from_cache += 1
                        if any([cached.get("city"), cached.get("country")]):
                            geocoded_count += 1
                        if (idx + 1) % 50 == 0:
                            logger.debug(f"  Batch progress: {idx + 1}/{len(batch_visits)} (cached: {batch_cached}, geocoded: {batch_geocoded})")
                    else:
                        # Need to geocode and save to place_locations
                        try:
                            loc = geocoder.reverse_geocode(visit["lat"], visit["lng"], place_id=place_id)
                            # Location data is saved to place_locations table via save_place_location
                            if any(loc.values()):
                                geocoded_count += 1
                                geocoded_from_api += 1
                                batch_geocoded += 1
                                logger.debug(f"  Geocoded visit {global_idx + 1}: {loc.get('city')}, {loc.get('country')}")
                            else:
                                # Geocoding returned no results, but we still need to save place_id
                                # to satisfy foreign key constraint (save minimal record with just lat/lng)
                                if place_id:
                                    geocoder.save_place_location_minimal(place_id, visit["lat"], visit["lng"])
                                    logger.debug(f"  Saved minimal place_id {place_id} (no location data)")
                                batch_errors += 1
                                geocode_errors += 1
                        except Exception as e:
                            batch_errors += 1
                            geocode_errors += 1
                            logger.warning(f"  Error geocoding visit {global_idx + 1} ({visit['lat']}, {visit['lng']}): {e}")
                            # Even if geocoding fails, save minimal record to satisfy foreign key
                            if place_id:
                                try:
                                    geocoder.save_place_location_minimal(place_id, visit["lat"], visit["lng"])
                                    logger.debug(f"  Saved minimal place_id {place_id} after geocoding error")
                                except Exception as save_error:
                                    logger.warning(f"  Failed to save minimal place_id {place_id}: {save_error}")
                
                batch_time = time.time() - batch_start_time
                batch_rate = len(batch_visits) / batch_time if batch_time > 0 else 0
                
                logger.info(f"  Batch {batch_num + 1} completed in {batch_time:.2f}s ({batch_rate:.1f} visits/sec)")
                logger.info(f"    - Cached: {batch_cached}, Geocoded: {batch_geocoded}, Errors: {batch_errors}")
                
                # Overall progress
                total_processed = batch_end_idx
                elapsed = time.time() - geocode_start
                overall_rate = total_processed / elapsed if elapsed > 0 else 0
                remaining = len(visits) - total_processed
                eta_seconds = remaining / overall_rate if overall_rate > 0 else 0
                eta_minutes = eta_seconds / 60
                
                logger.info(f"  Overall: {total_processed:,}/{len(visits):,} visits "
                          f"(cached: {geocoded_from_cache:,}, geocoded: {geocoded_from_api:,}, "
                          f"errors: {geocode_errors:,})")
                if eta_minutes > 0:
                    logger.info(f"  Estimated time remaining: {eta_minutes:.1f} minutes")
                
                # Commit place_locations after each batch to avoid losing data
                if conn and not dry_run:
                    try:
                        conn.commit()
                        logger.debug(f"  Committed place_locations updates for batch {batch_num + 1}")
                    except psycopg2.Error as e:
                        logger.warning(f"  Error committing batch {batch_num + 1}: {e}")
                        conn.rollback()
            
            geocode_time = time.time() - geocode_start
            avg_rate = len(visits) / geocode_time if geocode_time > 0 else 0
            logger.info(f"\n✓ Geocoding completed in {geocode_time:.2f} seconds ({avg_rate:.1f} visits/sec avg)")
            logger.info(f"  Summary: {geocoded_from_cache:,} from cache, {geocoded_from_api:,} from API, {geocode_errors:,} errors")
    else:
        logger.info("Skipping geocoding (per --skip-geocode)")

    if dry_run:
        logger.info("\n" + "=" * 60)
        logger.info("[DRY RUN] Would insert the following sample (first 5):")
        for i, visit in enumerate(visits[:5]):
            place_id = visit.get('place_id')
            # Try to get location from cache if available
            location_info = ""
            if place_id and conn and geocoder:
                cached = geocoder.get_place_location(place_id)
                if cached:
                    location_info = f" | city={cached.get('city')} country={cached.get('country')}"
            
            logger.info(
                f"  {i+1}. {visit['start_time']} | "
                f"lat={visit['lat']}, lng={visit['lng']} | "
                f"prob={visit['probability']} | "
                f"place_id={place_id}{location_info}"
            )
        if len(visits) > 5:
            logger.info(f"  ... and {len(visits) - 5:,} more")
        logger.info(f"\n  Geocoded visits (saved to place_locations): {geocoded_count:,}")
        if not skip_geocode:
            logger.info(f"    - From cache: {geocoded_from_cache:,}")
            logger.info(f"    - From API: {geocoded_from_api:,}")
        logger.info("\n  Note: Location data (city, state, country) is stored in place_locations table")
        logger.info("        and accessed via place_id foreign key relationship.")
        if conn:
            conn.close()
        logger.info("=" * 60)
        return
    
    # Connect to database and insert (if not already connected)
    if conn is None:
        logger.info("Connecting to database...")
        conn = get_db_connection()
    
    try:
        # Tables should already exist from schema.sql (Docker init)
        # Verify tables exist
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_name IN ('visits', 'place_locations')")
            table_count = cur.fetchone()[0]
            if table_count < 2:
                logger.warning(f"Warning: Expected 2 tables, found {table_count}. Schema may not be initialized.")
            else:
                logger.info("✓ Database tables verified")
        
        # Before inserting, ensure all place_ids exist in place_locations
        # to satisfy foreign key constraint
        logger.info("Verifying place_ids exist in place_locations before insert...")
        missing_place_ids = []
        with conn.cursor() as cur:
            for visit in visits:
                place_id = visit.get("place_id")
                if place_id:
                    # Check if place_id exists in place_locations
                    cur.execute("SELECT 1 FROM place_locations WHERE place_id = %s", (place_id,))
                    if not cur.fetchone():
                        missing_place_ids.append((place_id, visit["lat"], visit["lng"]))
        
        if missing_place_ids:
            # Deduplicate by place_id (keep first occurrence)
            seen_place_ids = set()
            unique_missing = []
            for place_id, lat, lng in missing_place_ids:
                if place_id not in seen_place_ids:
                    seen_place_ids.add(place_id)
                    unique_missing.append((place_id, lat, lng))
            
            logger.warning(f"Found {len(unique_missing)} unique place_ids not in place_locations, creating minimal records...")
            # Create minimal records for missing place_ids (lat/lng only, no city/country)
            with conn.cursor() as cur:
                for place_id, lat, lng in unique_missing:
                    cur.execute("""
                        INSERT INTO place_locations (
                            place_id, lat, lng, city, state, country, address, geocoded_at
                        )
                        VALUES (%s, %s, %s, NULL, NULL, NULL, NULL, NOW())
                        ON CONFLICT (place_id) DO NOTHING
                    """, (place_id, lat, lng))
            conn.commit()
            logger.info(f"✓ Created {len(unique_missing)} minimal place_locations records")
        
        logger.info(f"Inserting {len(visits):,} visits...")
        insert_start = time.time()

        insert_sql = """
        INSERT INTO visits (
            start_time,
            lat,
            lng,
            probability,
            place_id
        )
        VALUES (%s, %s, %s, %s, %s)
        """

        records = []
        for visit in visits:
            records.append(
                (
                    visit["start_time"],
                    visit["lat"],
                    visit["lng"],
                    visit["probability"],
                    visit["place_id"],
                )
            )
        
        with conn.cursor() as cur:
            execute_batch(cur, insert_sql, records, page_size=1000)
        
        conn.commit()
        insert_time = time.time() - insert_start
        logger.info(f"✓ Successfully inserted {len(visits):,} visits in {insert_time:.2f} seconds")
        
        # Print summary
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM visits")
            total_count = cur.fetchone()[0]
            logger.info(f"✓ Total visits in database: {total_count:,}")

        if not skip_geocode:
            logger.info(f"✓ Geocoded visits (non-null location): {geocoded_count:,}")
            logger.info(f"    - From cache: {geocoded_from_cache:,}")
            logger.info(f"    - From API: {geocoded_from_api:,}")
        
        # Print place_locations summary
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM place_locations")
            place_count = cur.fetchone()[0]
            logger.info(f"✓ Total unique places in cache: {place_count:,}")
        
        total_time = time.time() - start_time
        logger.info("=" * 60)
        logger.info(f"Import completed successfully in {total_time:.2f} seconds")
        logger.info("=" * 60)
    
    except psycopg2.Error as e:
        conn.rollback()
        logger.error(f"Error inserting data: {e}")
        sys.exit(1)
    finally:
        conn.close()
        logger.info("Database connection closed")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Import visit data from GoogleTimeline.json into Postgres'
    )
    parser.add_argument(
        '--json-file',
        default='data/GoogleTimeline.json',
        help='Path to GoogleTimeline.json file (default: data/GoogleTimeline.json)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview data without inserting into database'
    )
    parser.add_argument(
        '--skip-geocode',
        action='store_true',
        help='Skip reverse geocoding (only store lat/lng)'
    )
    
    args = parser.parse_args()
    
    # Resolve path relative to script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    json_path = os.path.join(project_root, args.json_file)
    
    if not os.path.exists(json_path):
        print(f"Error: JSON file not found: {json_path}")
        sys.exit(1)

    import_visits(json_path, dry_run=args.dry_run, skip_geocode=args.skip_geocode)


if __name__ == '__main__':
    main()

