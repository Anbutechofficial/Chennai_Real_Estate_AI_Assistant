import os
import math
import urllib.parse
import httpx
from typing import Optional, Dict, Any, List

# Pre-cached coordinates for prominent Chennai & TN real estate hubs for 0ms lookup
KNOWN_COORDINATES = {
    "t nagar": (13.0418, 80.2341),
    "t. nagar": (13.0418, 80.2341),
    "tnagar": (13.0418, 80.2341),
    "guindy": (13.0067, 80.2025),
    "adyar": (13.0012, 80.2565),
    "velachery": (12.9815, 80.2180),
    "anna nagar": (13.0850, 80.2101),
    "omr": (12.8710, 80.2260),
    "sholinganallur": (12.8988, 80.2274),
    "perungudi": (12.9654, 80.2461),
    "thiruvanmiyur": (12.9830, 80.2594),
    "besant nagar": (13.0003, 80.2667),
    "mylapore": (13.0368, 80.2676),
    "nungambakkam": (13.0569, 80.2425),
    "alwarpet": (13.0336, 80.2505),
    "egmore": (13.0784, 80.2608),
    "chennai central": (13.0827, 80.2707),
    "chennai airport": (12.9941, 80.1709),
    "airport": (12.9941, 80.1709),
    "porur": (13.0382, 80.1565),
    "tambaram": (12.9249, 80.1000),
    "chromepet": (12.9516, 80.1462),
    "pallavaram": (12.9675, 80.1491),
    "medavakkam": (12.9185, 80.1914),
    "pallikaranai": (12.9372, 80.2148),
    "perumbakkam": (12.8996, 80.1925),
    "vadapalani": (13.0500, 80.2121),
    "ashok nagar": (13.0373, 80.2123),
    "kodambakkam": (13.0524, 80.2255),
    "kilpauk": (13.0788, 80.2372),
    "ambattur": (13.1143, 80.1548),
    "mogappair": (13.0837, 80.1748),
    "poonamallee": (13.0487, 80.0935),
    "avadi": (13.1147, 80.1011),
    "perambur": (13.1075, 80.2434),
    "madhavaram": (13.1489, 80.2314),
    "kolathur": (13.1242, 80.2163),
    "siruseri": (12.8277, 80.2185),
    "kelambakkam": (12.7876, 80.2227),
    "navalur": (12.8465, 80.2259),
    "thiruporur": (12.7231, 80.1914),
    "ecr": (12.8550, 80.2450),
    "mahabalipuram": (12.6208, 80.1944),
    "coimbatore": (11.0168, 76.9558),
    "bangalore": (12.9716, 77.5946),
}

_geocode_cache: Dict[str, tuple[float, float]] = {}


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate direct distance between two coordinates in kilometers."""
    r = 6371.0  # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c


async def geocode_location(location_name: str) -> Optional[tuple[float, float]]:
    """
    Resolves location text to (latitude, longitude).
    Checks instant cache -> OpenStreetMap Nominatim (Free, no API key required).
    """
    cleaned = location_name.strip().lower().replace(".", "")
    if cleaned in KNOWN_COORDINATES:
        return KNOWN_COORDINATES[cleaned]

    # Partial substring check in known locations
    for k, coords in KNOWN_COORDINATES.items():
        if k in cleaned or cleaned in k:
            return coords

    if cleaned in _geocode_cache:
        return _geocode_cache[cleaned]

    # Free OpenStreetMap Nominatim Geocoder fallback
    try:
        search_query = location_name
        if "chennai" not in search_query.lower() and "tamil nadu" not in search_query.lower():
            search_query += ", Chennai, Tamil Nadu, India"

        encoded = urllib.parse.quote(search_query)
        url = f"https://nominatim.openstreetmap.org/search?q={encoded}&format=json&limit=1"
        headers = {"User-Agent": "RealEstateAIAssistant/1.0 (contact@realestateai.local)"}

        async with httpx.AsyncClient(timeout=4.0) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                if data and len(data) > 0:
                    lat = float(data[0]["lat"])
                    lon = float(data[0]["lon"])
                    _geocode_cache[cleaned] = (lat, lon)
                    return (lat, lon)
    except Exception as e:
        print(f"[MapsService] Geocode lookup note for '{location_name}': {e}")

    # Default fallback to Chennai center if unresolvable
    return (13.0827, 80.2707)


def get_google_maps_directions_url(origin: str, destination: str, travel_mode: str = "driving") -> str:
    """Generates standard zero-cost Google Maps universal navigation deep link."""
    base_url = "https://www.google.com/maps/dir/?api=1"
    params = {
        "origin": origin.strip(),
        "destination": destination.strip(),
        "travelmode": travel_mode if travel_mode in ["driving", "transit", "walking", "bicycling"] else "driving"
    }
    return f"{base_url}&{urllib.parse.urlencode(params)}"


def get_google_maps_place_url(place_name: str) -> str:
    """Generates Google Maps search / pin URL for a location."""
    return f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(place_name.strip())}"


async def calculate_distance_and_route(
    origin: str,
    destination: str,
    travel_mode: str = "driving"
) -> Dict[str, Any]:
    """
    Computes road distance, travel duration, route highlights, and creates a Google Maps navigation link.
    100% Free & No API key needed (uses OSRM routing engine + Google Universal deep links).
    """
    coords_orig = await geocode_location(origin)
    coords_dest = await geocode_location(destination)

    # Standard Google Maps universal link
    maps_url = get_google_maps_directions_url(origin, destination, travel_mode)

    if not coords_orig or not coords_dest:
        return {
            "origin": origin,
            "destination": destination,
            "distance_km": "Unknown",
            "duration_mins": "Unknown",
            "travel_mode": travel_mode,
            "google_maps_url": maps_url,
            "note": "Could not precisely geocode coordinates, but Google Maps link is provided."
        }

    lat1, lon1 = coords_orig
    lat2, lon2 = coords_dest

    # Call Free OSRM Public Routing API
    try:
        osrm_profile = "driving" if travel_mode in ["driving", "two_wheeler"] else travel_mode
        osrm_url = f"http://router.project-osrm.org/route/v1/{osrm_profile}/{lon1},{lat1};{lon2},{lat2}?overview=false"

        async with httpx.AsyncClient(timeout=3.5) as client:
            resp = await client.get(osrm_url)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("code") == "Ok" and data.get("routes"):
                    route = data["routes"][0]
                    distance_km = round(route["distance"] / 1000.0, 1)
                    duration_mins = max(1, round(route["duration"] / 60.0))

                    return {
                        "origin": origin,
                        "destination": destination,
                        "distance_km": f"{distance_km} km",
                        "duration_mins": f"{duration_mins} mins",
                        "travel_mode": travel_mode,
                        "route_summary": f"Estimated {distance_km} km via fastest road route ({duration_mins} mins {travel_mode})",
                        "google_maps_url": maps_url,
                        "status": "success"
                    }
    except Exception as ex:
        print(f"[MapsService] OSRM routing fallback: {ex}")

    # Fallback to direct Haversine distance with typical city traffic factor (1.3x road winding factor)
    direct_km = haversine_distance_km(lat1, lon1, lat2, lon2)
    est_road_km = round(direct_km * 1.32, 1)
    
    # Approx city speed 25 km/h for driving, 4 km/h for walking
    speed_kmh = 28.0 if travel_mode == "driving" else 4.5
    est_duration_mins = max(2, round((est_road_km / speed_kmh) * 60))

    return {
        "origin": origin,
        "destination": destination,
        "distance_km": f"{est_road_km} km",
        "duration_mins": f"{est_duration_mins} mins",
        "travel_mode": travel_mode,
        "route_summary": f"Approx {est_road_km} km ({est_duration_mins} mins {travel_mode})",
        "google_maps_url": maps_url,
        "status": "success"
    }


async def get_nearby_amenities(location: str, amenity_type: str = "metro") -> Dict[str, Any]:
    """
    Discovers key amenities (Metro, Hospitals, Schools, IT Parks) around a given property locality.
    """
    loc_clean = location.strip().lower()
    maps_search_url = get_google_maps_place_url(f"{amenity_type} near {location}")

    amenity_database = {
        "metro": [
            {"name": "Chennai Central Metro", "location": "Park Town", "line": "Blue / Green Line"},
            {"name": "Guindy Metro Station", "location": "Guindy", "line": "Blue Line"},
            {"name": "AG-DMS Metro Station", "location": "T Nagar / Anna Salai", "line": "Blue Line"},
            {"name": "Anna Nagar Tower Metro", "location": "Anna Nagar", "line": "Green Line"},
            {"name": "Airport Metro Station", "location": "Meenambakkam", "line": "Blue Line"},
            {"name": "Thirumangalam Metro", "location": "Anna Nagar West", "line": "Green Line"},
            {"name": "Saidapet Metro Station", "location": "Saidapet", "line": "Blue Line"},
            {"name": "Vadapalani Metro Station", "location": "Vadapalani", "line": "Green Line"},
        ],
        "hospital": [
            {"name": "Apollo Hospitals", "location": "Greams Road & OMR", "specialty": "Multi-Specialty"},
            {"name": "Fortis Malar Hospital", "location": "Adyar", "specialty": "Multi-Specialty"},
            {"name": "MIOT International", "location": "Manapakkam / Porur", "specialty": "Orthopaedics & Trauma"},
            {"name": "Gleneagles Global Health City", "location": "Perumbakkam / OMR", "specialty": "Multi-Specialty"},
            {"name": "Kauvery Hospital", "location": "Alwarpet & Vadapalani", "specialty": "Multi-Specialty"},
        ],
        "school": [
            {"name": "DAV Public School", "location": "Velachery / Mogappair", "board": "CBSE"},
            {"name": "Chettinad Vidyashram", "location": "R.A. Puram", "board": "CBSE"},
            {"name": "SBOA School and Junior College", "location": "Anna Nagar", "board": "CBSE"},
            {"name": "Bala Vidya Mandir", "location": "Adyar", "board": "CBSE"},
            {"name": "The School - KFI", "location": "Thiruvanmiyur", "board": "Krishnamurti Foundation"},
        ],
        "it_park": [
            {"name": "TIDEL Park", "location": "Taramani / OMR", "type": "IT SEZ"},
            {"name": "DLF Cybercity", "location": "Manapakkam / Porur", "type": "IT SEZ"},
            {"name": "Olympia Tech Park", "location": "Guindy", "type": "IT Park"},
            {"name": "SIPCOT IT Park", "location": "Siruseri, OMR", "type": "IT SEZ"},
            {"name": "Ramanujan IT City", "location": "Taramani", "type": "Special Economic Zone"},
        ]
    }

    # Find matching amenity category
    category = "metro"
    if any(w in amenity_type.lower() for w in ["hospital", "clinic", "medical"]):
        category = "hospital"
    elif any(w in amenity_type.lower() for w in ["school", "college", "education"]):
        category = "school"
    elif any(w in amenity_type.lower() for w in ["it park", "office", "tech park", "workplace"]):
        category = "it_park"

    places = amenity_database.get(category, amenity_database["metro"])

    # Calculate distance from property location to each amenity
    prop_coords = await geocode_location(location)
    results = []

    if prop_coords:
        plat, plon = prop_coords
        for p in places:
            p_coords = await geocode_location(p["location"])
            if p_coords:
                alat, alon = p_coords
                dist_km = round(haversine_distance_km(plat, plon, alat, alon) * 1.3, 1)
                results.append({
                    "name": p["name"],
                    "locality": p["location"],
                    "approx_distance": f"{dist_km} km",
                    "info": p.get("line") or p.get("specialty") or p.get("board") or p.get("type", "")
                })

        results.sort(key=lambda x: float(x["approx_distance"].replace(" km", "")))

    return {
        "property_location": location,
        "amenity_type": category,
        "nearby_places": results[:4],
        "google_maps_search_url": maps_search_url
    }
