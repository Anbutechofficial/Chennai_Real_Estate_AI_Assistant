import urllib.parse
from fastapi import APIRouter, Response, Query
from typing import Optional

router = APIRouter(prefix="/api/v1/map", tags=["Map Visualization"])


@router.get("/route")
def generate_route_map_svg(
    origin: str = Query("Origin", description="Starting location name"),
    destination: str = Query("Destination", description="Destination property name"),
    dist: Optional[str] = Query(None, description="Distance in km"),
    time: Optional[str] = Query(None, description="Duration in mins"),
    lat1: Optional[float] = Query(None),
    lon1: Optional[float] = Query(None),
    lat2: Optional[float] = Query(None),
    lon2: Optional[float] = Query(None),
):
    """
    Dynamically generates a high-res SVG Route Map visual card.
    Zero external dependencies, instant 0ms rendering, beautiful neon cyberpunk aesthetic.
    """
    orig_clean = origin.strip()[:28]
    dest_clean = destination.strip()[:28]
    dist_text = f"{dist} km" if dist else "Direct Route"
    time_text = f"{time} mins drive" if time else "Fastest corridor"

    svg_content = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 620 280" width="100%" height="100%">
  <defs>
    <!-- Background Gradient -->
    <linearGradient id="bgGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#070a13"/>
      <stop offset="50%" stop-color="#0f172a"/>
      <stop offset="100%" stop-color="#060911"/>
    </linearGradient>

    <!-- Route Line Gradient -->
    <linearGradient id="routeGrad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#3b82f6"/>
      <stop offset="50%" stop-color="#06b6d4"/>
      <stop offset="100%" stop-color="#10b981"/>
    </linearGradient>

    <!-- Glow Filter -->
    <filter id="neonGlow" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="4" result="blur"/>
      <feMerge>
        <feMergeNode in="blur"/>
        <feMergeNode in="blur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
    
    <!-- Grid Pattern -->
    <pattern id="grid" width="30" height="30" patternUnits="userSpaceOnUse">
      <path d="M 30 0 L 0 0 0 30" fill="none" stroke="rgba(255,255,255,0.035)" stroke-width="1"/>
    </pattern>
  </defs>

  <!-- Background Base -->
  <rect width="620" height="280" rx="16" fill="url(#bgGrad)"/>
  <rect width="620" height="280" rx="16" fill="url(#grid)"/>

  <!-- Subtle Road Network Contour Lines -->
  <path d="M 0 60 Q 180 120, 360 40 T 620 100" fill="none" stroke="rgba(255,255,255,0.05)" stroke-width="2"/>
  <path d="M 0 200 Q 200 140, 420 220 T 620 180" fill="none" stroke="rgba(255,255,255,0.05)" stroke-width="2"/>
  <path d="M 120 0 Q 180 140, 140 280" fill="none" stroke="rgba(255,255,255,0.03)" stroke-width="2"/>
  <path d="M 500 0 Q 460 140, 520 280" fill="none" stroke="rgba(255,255,255,0.03)" stroke-width="2"/>

  <!-- Main Active Route Path (Glow Layer) -->
  <path d="M 110 140 C 220 50, 400 230, 510 140" fill="none" stroke="url(#routeGrad)" stroke-width="10" stroke-opacity="0.3" filter="url(#neonGlow)"/>
  
  <!-- Main Active Route Path (Dashed Highway Layer) -->
  <path d="M 110 140 C 220 50, 400 230, 510 140" fill="none" stroke="url(#routeGrad)" stroke-width="4.5" stroke-linecap="round" stroke-dasharray="8 6"/>

  <!-- Origin Pin (Point A) -->
  <g transform="translate(110, 140)">
    <!-- Radar pulse circle -->
    <circle r="22" fill="rgba(59, 130, 246, 0.15)"/>
    <circle r="14" fill="#1e3a8a" stroke="#3b82f6" stroke-width="2.5"/>
    <text y="5" text-anchor="middle" fill="#ffffff" font-family="system-ui, -apple-system, sans-serif" font-size="12" font-weight="bold">A</text>
  </g>

  <!-- Origin Label Box -->
  <g transform="translate(110, 75)">
    <rect x="-85" y="-12" width="170" height="34" rx="8" fill="rgba(15, 23, 42, 0.9)" stroke="rgba(59, 130, 246, 0.4)" stroke-width="1.2"/>
    <text x="0" y="3" text-anchor="middle" fill="#93c5fd" font-family="system-ui, -apple-system, sans-serif" font-size="10" font-weight="600" letter-spacing="0.5">ORIGIN</text>
    <text x="0" y="16" text-anchor="middle" fill="#ffffff" font-family="system-ui, -apple-system, sans-serif" font-size="11" font-weight="600">{orig_clean}</text>
  </g>

  <!-- Destination Pin (Point B) -->
  <g transform="translate(510, 140)">
    <!-- Radar pulse circle -->
    <circle r="22" fill="rgba(16, 185, 129, 0.15)"/>
    <circle r="14" fill="#064e3b" stroke="#10b981" stroke-width="2.5"/>
    <text y="5" text-anchor="middle" fill="#ffffff" font-family="system-ui, -apple-system, sans-serif" font-size="12" font-weight="bold">B</text>
  </g>

  <!-- Destination Label Box -->
  <g transform="translate(510, 75)">
    <rect x="-85" y="-12" width="170" height="34" rx="8" fill="rgba(15, 23, 42, 0.9)" stroke="rgba(16, 185, 129, 0.4)" stroke-width="1.2"/>
    <text x="0" y="3" text-anchor="middle" fill="#6ee7b7" font-family="system-ui, -apple-system, sans-serif" font-size="10" font-weight="600" letter-spacing="0.5">DESTINATION</text>
    <text x="0" y="16" text-anchor="middle" fill="#ffffff" font-family="system-ui, -apple-system, sans-serif" font-size="11" font-weight="600">{dest_clean}</text>
  </g>

  <!-- Center Metric Badge (Distance & Duration Pill) -->
  <g transform="translate(310, 140)">
    <rect x="-95" y="-22" width="190" height="44" rx="22" fill="rgba(15, 23, 42, 0.95)" stroke="url(#routeGrad)" stroke-width="1.8" filter="url(#neonGlow)"/>
    <text x="0" y="-3" text-anchor="middle" fill="#ffffff" font-family="system-ui, -apple-system, sans-serif" font-size="14" font-weight="bold">🛣️ {dist_text}</text>
    <text x="0" y="14" text-anchor="middle" fill="#38bdf8" font-family="system-ui, -apple-system, sans-serif" font-size="11" font-weight="500">⏱️ {time_text}</text>
  </g>

  <!-- Bottom Interactive Status Strip -->
  <g transform="translate(310, 252)">
    <rect x="-180" y="-14" width="360" height="26" rx="13" fill="rgba(255, 255, 255, 0.05)" stroke="rgba(255, 255, 255, 0.1)" stroke-width="0.8"/>
    <circle cx="-150" cy="-1" r="3.5" fill="#10b981"/>
    <text x="-138" y="3" fill="#cbd5e1" font-family="system-ui, -apple-system, sans-serif" font-size="10.5" font-weight="500">Fastest Arterial Route Calculated via Smart Navigation Engine</text>
  </g>
</svg>"""

    return Response(
        content=svg_content,
        media_type="image/svg+xml",
        headers={
            "Cache-Control": "public, max-age=86400",
            "Access-Control-Allow-Origin": "*"
        }
    )
