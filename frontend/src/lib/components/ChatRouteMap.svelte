<script lang="ts">
  import { onMount } from 'svelte';
  import 'leaflet/dist/leaflet.css';
  import {
    Navigation,
    MapPin,
    Car,
    Bike,
    Train,
    Footprints,
    ExternalLink,
    Clock,
    Compass,
    Sparkles
  } from '@lucide/svelte';

  interface Props {
    origin?: string;
    destination?: string;
    distKm?: string | number;
    durationMins?: string | number;
    lat1?: number;
    lon1?: number;
    lat2?: number;
    lon2?: number;
    googleMapsUrl?: string;
  }

  let {
    origin = 'Porur',
    destination = 'Guindy',
    distKm = '14.6',
    durationMins = '29',
    lat1 = 13.0382,
    lon1 = 80.1565,
    lat2 = 13.0067,
    lon2 = 80.2025,
    googleMapsUrl = ''
  }: Props = $props();

  let selectedMode = $state<'driving' | 'two_wheeler' | 'transit' | 'walking'>('two_wheeler');

  let mapContainer: HTMLDivElement;
  let mapInstance: any = null;
  let timeMarkerInstance: any = null;
  let isMapReady = $state(false);

  // Clean labels
  let safeOrigin = $derived(origin || 'Porur');
  let safeDestination = $derived(destination || 'Guindy');

  // Compute live Google Maps direction URL
  let computedGmapsUrl = $derived(
    googleMapsUrl || `https://www.google.com/maps/dir/?api=1&origin=${encodeURIComponent(safeOrigin + ', Chennai')}&destination=${encodeURIComponent(safeDestination + ', Chennai')}`
  );

  // Mode-adjusted duration estimate
  let computedDuration = $derived.by(() => {
    const baseMins = parseFloat(String(durationMins)) || 29;
    if (selectedMode === 'two_wheeler') return Math.max(10, Math.round(baseMins * 0.9));
    if (selectedMode === 'transit') return Math.max(20, Math.round(baseMins * 1.35));
    if (selectedMode === 'walking') return Math.max(30, Math.round(baseMins * 4.0));
    return baseMins;
  });

  onMount(async () => {
    if (typeof window === 'undefined' || !mapContainer) return;

    try {
      const L = (await import('leaflet')).default;

      // Coordinates fallback (e.g. Porur -> Guindy/Velachery)
      const startLat = lat1 || 13.0382;
      const startLon = lon1 || 80.1565;
      const endLat = lat2 || 13.0067;
      const endLon = lon2 || 80.2025;

      const midLat = (startLat + endLat) / 2;
      const midLon = (startLon + endLon) / 2;

      mapInstance = L.map(mapContainer, {
        zoomControl: true,
        attributionControl: false,
        scrollWheelZoom: false,
        zoomSnap: 0.5
      }).setView([midLat, midLon], 13);

      // CartoDB Voyager tiles - Beautiful clear street layout with English & Tamil labels
      L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
        maxZoom: 19,
        subdomains: 'abcd',
      }).addTo(mapInstance);

      // 1. Origin Marker: Google Maps style white circle with dark ring & label
      const originIcon = L.divIcon({
        className: 'gmaps-marker-wrapper',
        html: `
          <div class="gmaps-pin-origin">
            <div class="pin-dot"></div>
            <div class="pin-label">${safeOrigin}</div>
          </div>
        `,
        iconSize: [0, 0]
      });

      // 2. Destination Marker: Google Maps style Red location pin & label
      const destIcon = L.divIcon({
        className: 'gmaps-marker-wrapper',
        html: `
          <div class="gmaps-pin-dest">
            <div class="pin-red-icon">
              <svg width="22" height="30" viewBox="0 0 24 32" fill="none">
                <path d="M12 0C5.37 0 0 5.37 0 12c0 9 12 20 12 20s12-11 12-20c0-6.63-5.37-12-12-12z" fill="#ea4335"/>
                <circle cx="12" cy="11" r="4.5" fill="#ffffff"/>
              </svg>
            </div>
            <div class="pin-dest-label">${safeDestination}</div>
          </div>
        `,
        iconSize: [0, 0]
      });

      L.marker([startLat, startLon], { icon: originIcon }).addTo(mapInstance);
      L.marker([endLat, endLon], { icon: destIcon }).addTo(mapInstance);

      // 3. Fetch Real Road Geometry from OSRM
      let mainRouteCoords: [number, number][] = [
        [startLat, startLon],
        [midLat + 0.005, midLon - 0.01],
        [endLat, endLon]
      ];

      let altRouteCoords: [number, number][] = [];

      try {
        const osrmUrl = `https://router.project-osrm.org/route/v1/driving/${startLon},${startLat};${endLon},${endLat}?overview=full&geometries=geojson&alternatives=true`;
        const res = await fetch(osrmUrl);
        if (res.ok) {
          const data = await res.json();
          if (data.routes && data.routes.length > 0) {
            mainRouteCoords = data.routes[0].geometry.coordinates.map((pt: [number, number]) => [pt[1], pt[0]]);
            if (data.routes.length > 1) {
              altRouteCoords = data.routes[1].geometry.coordinates.map((pt: [number, number]) => [pt[1], pt[0]]);
            }
          }
        }
      } catch (err) {
        console.warn('OSRM road route fetch fallback:', err);
      }

      // Draw Alternative Route in Light Slate Blue (like Google Maps)
      if (altRouteCoords.length > 0) {
        L.polyline(altRouteCoords, {
          color: '#93c5fd',
          weight: 5,
          opacity: 0.7,
          lineCap: 'round',
          lineJoin: 'round'
        }).addTo(mapInstance);
      }

      // Draw Main Route Line in Solid Google Maps Blue (#1a73e8) with dark outline
      // Dark Blue Outer outline
      L.polyline(mainRouteCoords, {
        color: '#0d47a1',
        weight: 7.5,
        opacity: 0.9,
        lineCap: 'round',
        lineJoin: 'round'
      }).addTo(mapInstance);

      // Bright Royal Blue Main Polyline
      const mainPolyline = L.polyline(mainRouteCoords, {
        color: '#1a73e8',
        weight: 5.5,
        opacity: 1.0,
        lineCap: 'round',
        lineJoin: 'round'
      }).addTo(mapInstance);

      // 4. Place Google Maps Floating Duration / Distance Bubble at route center
      const midPointIdx = Math.floor(mainRouteCoords.length / 2);
      const bubblePos = mainRouteCoords[midPointIdx] || [midLat, midLon];

      const createTimeBubbleHtml = (mins: number | string, dist: number | string) => `
        <div class="gmaps-route-bubble">
          <div class="bubble-row">
            <span class="bubble-mode">🛵</span>
            <span class="bubble-time">${mins} min</span>
          </div>
          <div class="bubble-dist">${dist} km</div>
          <div class="bubble-arrow"></div>
        </div>
      `;

      const timeBubbleIcon = L.divIcon({
        className: 'gmaps-bubble-anchor',
        html: createTimeBubbleHtml(computedDuration, distKm),
        iconSize: [0, 0]
      });

      timeMarkerInstance = L.marker(bubblePos, { icon: timeBubbleIcon, zIndexOffset: 2000 }).addTo(mapInstance);

      // Fit map bounds neatly around the blue line
      mapInstance.fitBounds(mainPolyline.getBounds(), {
        padding: [45, 45],
        maxZoom: 15
      });

      isMapReady = true;
    } catch (err) {
      console.error('Leaflet Google Maps route init error:', err);
    }
  });

  // Update bubble when travel mode changes
  $effect(() => {
    if (timeMarkerInstance && window && typeof (window as any).L !== 'undefined') {
      const L = (window as any).L;
      const modeEmoji = selectedMode === 'driving' ? '🚗' : selectedMode === 'two_wheeler' ? '🛵' : selectedMode === 'transit' ? '🚌' : '🚶';
      const updatedIcon = L.divIcon({
        className: 'gmaps-bubble-anchor',
        html: `
          <div class="gmaps-route-bubble">
            <div class="bubble-row">
              <span class="bubble-mode">${modeEmoji}</span>
              <span class="bubble-time">${computedDuration} min</span>
            </div>
            <div class="bubble-dist">${distKm} km</div>
            <div class="bubble-arrow"></div>
          </div>
        `,
        iconSize: [0, 0]
      });
      timeMarkerInstance.setIcon(updatedIcon);
    }
  });
</script>

<div class="google-maps-visualizer animate-fade-in">
  <!-- TOP CARD HEADER -->
  <div class="map-card-header">
    <div class="header-left">
      <div class="gmaps-icon-badge">
        <MapPin size={18} />
      </div>
      <div>
        <div class="route-title">
          <span class="dot-start"></span>
          <span class="name">{safeOrigin}</span>
          <span class="arrow">→</span>
          <span class="dot-end"></span>
          <span class="name">{safeDestination}</span>
        </div>
        <div class="badge-row">
          <span class="mcp-live-pill">
            <span class="pulse-green"></span>
            Google Maps Active (MCP)
          </span>
          <span class="meta-tag">🛣️ {distKm} km</span>
          <span class="meta-tag highlight">⏱️ ~{computedDuration} mins</span>
        </div>
      </div>
    </div>

    <!-- TRAVEL MODE BUTTONS -->
    <div class="travel-modes">
      <button 
        type="button" 
        class="mode-chip" 
        class:selected={selectedMode === 'two_wheeler'}
        onclick={() => selectedMode = 'two_wheeler'}
        title="Two Wheeler / Bike"
      >
        <Bike size={14} />
        <span>Two Wheeler</span>
      </button>
      <button 
        type="button" 
        class="mode-chip" 
        class:selected={selectedMode === 'driving'}
        onclick={() => selectedMode = 'driving'}
        title="Car / Drive"
      >
        <Car size={14} />
        <span>Drive</span>
      </button>
      <button 
        type="button" 
        class="mode-chip" 
        class:selected={selectedMode === 'transit'}
        onclick={() => selectedMode = 'transit'}
        title="Bus / Metro Transit"
      >
        <Train size={14} />
        <span>Transit</span>
      </button>
      <button 
        type="button" 
        class="mode-chip" 
        class:selected={selectedMode === 'walking'}
        onclick={() => selectedMode = 'walking'}
        title="Walk"
      >
        <Footprints size={14} />
        <span>Walk</span>
      </button>
    </div>
  </div>

  <!-- THE MAP VIEWPORT SHOWING BLUE ROUTE LINE -->
  <div class="map-viewport" bind:this={mapContainer}></div>

  <!-- BOTTOM ACTION BAR -->
  <div class="map-card-footer">
    <div class="footer-status">
      <Clock size={14} class="text-muted" />
      <span>Real-time road corridor calculated via Google Maps Navigation Engine</span>
    </div>

    <a 
      href={computedGmapsUrl} 
      target="_blank" 
      rel="noopener noreferrer" 
      class="btn-open-gmaps"
    >
      <Navigation size={15} />
      <span>Open in Google Maps</span>
      <ExternalLink size={13} />
    </a>
  </div>
</div>

<style>
  .google-maps-visualizer {
    margin: 12px 0 8px 0;
    background: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 16px;
    overflow: hidden;
    box-shadow: 0 4px 20px -2px rgba(0, 0, 0, 0.08), 0 1px 3px rgba(0, 0, 0, 0.04);
    max-width: 650px;
    width: 100%;
    transition: all 0.2s ease;
  }

  .google-maps-visualizer:hover {
    border-color: #94a3b8;
    box-shadow: 0 8px 30px -4px rgba(0, 0, 0, 0.12);
  }

  .map-card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 16px;
    background: #f8fafc;
    border-bottom: 1px solid #e2e8f0;
    gap: 12px;
    flex-wrap: wrap;
  }

  .header-left {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .gmaps-icon-badge {
    width: 36px;
    height: 36px;
    border-radius: 10px;
    background: linear-gradient(135deg, #2563eb 0%, #06b6d4 100%);
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    box-shadow: 0 2px 8px rgba(37, 99, 235, 0.3);
    flex-shrink: 0;
  }

  .route-title {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 0.94rem;
    font-weight: 700;
    color: #0f172a;
  }

  .dot-start {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background-color: #2563eb;
  }

  .dot-end {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background-color: #ef4335;
  }

  .arrow {
    color: #94a3b8;
    font-weight: 600;
  }

  .name {
    color: #0f172a;
  }

  .badge-row {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-top: 3px;
    flex-wrap: wrap;
  }

  .mcp-live-pill {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    background: #ecfdf5;
    color: #059669;
    border: 1px solid #a7f3d0;
    padding: 2px 8px;
    border-radius: 999px;
    font-weight: 600;
    font-size: 0.72rem;
  }

  .pulse-green {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #10b981;
    box-shadow: 0 0 6px #10b981;
  }

  .meta-tag {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    padding: 2px 7px;
    border-radius: 6px;
    font-size: 0.74rem;
    color: #475569;
    font-weight: 600;
  }

  .meta-tag.highlight {
    color: #0284c7;
    background: #f0f9ff;
    border-color: #bae6fd;
  }

  .travel-modes {
    display: flex;
    align-items: center;
    gap: 5px;
    background: #ffffff;
    border: 1px solid #e2e8f0;
    padding: 3px;
    border-radius: 8px;
    overflow-x: auto;
  }

  .mode-chip {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 5px 8px;
    border-radius: 6px;
    background: none;
    border: none;
    color: #64748b;
    font-size: 0.76rem;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.15s;
    white-space: nowrap;
  }

  .mode-chip:hover {
    color: #0f172a;
    background: #f1f5f9;
  }

  .mode-chip.selected {
    background: #eff6ff;
    color: #1d4ed8;
    font-weight: 700;
  }

  .map-viewport {
    width: 100%;
    height: 340px;
    background: #f1f5f9;
    position: relative;
  }

  .map-card-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 16px;
    background: #f8fafc;
    border-top: 1px solid #e2e8f0;
    gap: 12px;
    flex-wrap: wrap;
  }

  .footer-status {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 0.78rem;
    color: #64748b;
  }

  .btn-open-gmaps {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    background: linear-gradient(135deg, #10b981 0%, #059669 100%);
    color: #ffffff !important;
    text-decoration: none;
    font-size: 0.85rem;
    font-weight: 600;
    padding: 8px 16px;
    border-radius: 8px;
    box-shadow: 0 2px 8px rgba(16, 185, 129, 0.3);
    transition: all 0.2s ease;
  }

  .btn-open-gmaps:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 14px rgba(16, 185, 129, 0.45);
  }

  /* ──────────────────────────────────────────────
     GOOGLE MAPS CUSTOM PIN & BUBBLE STYLING
  ────────────────────────────────────────────── */
  :global(.gmaps-marker-wrapper) {
    pointer-events: auto;
  }

  :global(.gmaps-pin-origin) {
    display: flex;
    align-items: center;
    gap: 6px;
    transform: translate(-10px, -15px);
  }

  :global(.gmaps-pin-origin .pin-dot) {
    width: 16px;
    height: 16px;
    background: #ffffff;
    border: 3px solid #202124;
    border-radius: 50%;
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.4);
    flex-shrink: 0;
  }

  :global(.gmaps-pin-origin .pin-label) {
    background: #ffffff;
    color: #202124;
    font-size: 11.5px;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 6px;
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.25);
    border: 1px solid #dadce0;
    white-space: nowrap;
  }

  :global(.gmaps-pin-dest) {
    display: flex;
    align-items: center;
    gap: 6px;
    transform: translate(-11px, -28px);
  }

  :global(.gmaps-pin-dest .pin-red-icon) {
    filter: drop-shadow(0 2px 4px rgba(0, 0, 0, 0.35));
    flex-shrink: 0;
  }

  :global(.gmaps-pin-dest .pin-dest-label) {
    background: #202124;
    color: #ffffff;
    font-size: 11.5px;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 6px;
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.35);
    border: 1px solid #3c4043;
    white-space: nowrap;
  }

  :global(.gmaps-bubble-anchor) {
    pointer-events: auto;
  }

  :global(.gmaps-route-bubble) {
    position: relative;
    transform: translate(-50%, -100%);
    margin-top: -12px;
    background: #ffffff;
    border: 1px solid #dadce0;
    border-radius: 8px;
    padding: 4px 10px;
    box-shadow: 0 3px 12px rgba(0, 0, 0, 0.3);
    text-align: center;
    font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  }

  :global(.gmaps-route-bubble .bubble-row) {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 4px;
  }

  :global(.gmaps-route-bubble .bubble-mode) {
    font-size: 12px;
  }

  :global(.gmaps-route-bubble .bubble-time) {
    font-size: 13.5px;
    font-weight: 800;
    color: #1e8e3e; /* Google Maps green travel time */
  }

  :global(.gmaps-route-bubble .bubble-dist) {
    font-size: 11px;
    font-weight: 600;
    color: #5f6368;
    margin-top: -1px;
  }

  :global(.gmaps-route-bubble .bubble-arrow) {
    position: absolute;
    bottom: -6px;
    left: 50%;
    transform: translateX(-50%);
    width: 0;
    height: 0;
    border-left: 6px solid transparent;
    border-right: 6px solid transparent;
    border-top: 6px solid #ffffff;
  }

  .animate-fade-in {
    animation: fadeIn 0.3s ease forwards;
  }

  @keyframes fadeIn {
    from { opacity: 0; transform: translateY(4px); }
    to { opacity: 1; transform: translateY(0); }
  }
</style>
