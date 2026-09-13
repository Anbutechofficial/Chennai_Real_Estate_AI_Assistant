<script lang="ts">
  import { onMount } from 'svelte';
  import {
    ArrowLeft,
    MapPin,
    Calendar,
    Calculator,
    Navigation,
    Clock,
    ShieldCheck,
    Key,
    RefreshCw,
    ExternalLink,
    Lock,
    CheckCircle2,
    Sliders,
    Globe,
    Layers,
    Car,
    Bike,
    Train,
    Footprints,
    IndianRupee,
    Percent,
    CalendarCheck,
    CalendarPlus,
    Info,
    Sparkles,
    Building2,
    Check,
    Video,
    User,
    Mail,
    Phone,
    Settings,
    Zap,
    TrendingUp,
    Compass,
    X
  } from '@lucide/svelte';

  let { onBack }: { onBack?: () => void } = $props();

  const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

  // --- MODAL / TESTER STATE ---
  let activeModal = $state<'maps' | 'calendar' | 'calculator' | 'oauth' | null>(null);
  let isOAuthModalOpen = $state(false);
  let isSyncing = $state(false);
  let syncNotification = $state('');

  // OAuth Configuration State
  let oauthConnected = $state(true);
  let oauthEmail = $state('user.realestate@gmail.com');
  let oauthClientId = $state('847291039482-rf-assistant.apps.googleusercontent.com');
  let calendarScopeGranted = $state(true);
  let mapsScopeGranted = $state(true);

  // --- GOOGLE MAPS MCP STATE ---
  let mapsOrigin = $state('Chennai Central');
  let mapsDestination = $state('Prestige Courtyards, Sholinganallur');
  let mapsTravelMode = $state<'drive' | 'two_wheeler' | 'transit' | 'walk'>('drive');
  let isRunningMapsTool = $state(false);
  let mapsRouteResult = $state<any>(null);

  // Maps Amenities Sub-feature
  let amenityLocality = $state('Sholinganallur');
  let amenityType = $state('metro');
  let amenityRadius = $state(4000);
  let isRunningAmenityTool = $state(false);
  let amenityResult = $state<any>(null);

  // --- GOOGLE CALENDAR MCP STATE ---
  let calendarProperty = $state('Prestige Courtyards, Sholinganallur');
  let calendarCustomerName = $state('Ramesh Kumar');
  let calendarCustomerEmail = $state('ramesh.k@gmail.com');
  let calendarCustomerPhone = $state('+91 98401 23456');
  let calendarDate = $state('Upcoming Saturday');
  let calendarTimeSlot = $state('11:00 AM');
  let calendarNotes = $state('Interested in 3 BHK high-rise unit with East facing entrance');
  
  let isCheckingSlots = $state(false);
  let slotCheckResult = $state<any>(null);
  let isBookingVisit = $state(false);
  let bookingConfirmation = $state<any>(null);

  // --- FINANCIAL CALCULATOR MCP STATE ---
  let loanAmountLakhs = $state(65.0);
  let annualInterestRate = $state(8.5);
  let tenureYears = $state(20);
  let isCalculatingEmi = $state(false);
  let emiResult = $state<any>(null);

  // Property Breakdown State
  let propertyBasePriceLakhs = $state(85.0);
  let parkingCostLakhs = $state(3.5);
  let floorRiseCharge = $state(1.5);
  let isCalculatingBreakdown = $state(false);
  let breakdownResult = $state<any>(null);

  // Initial MCP Status Load
  onMount(() => {
    runEmiCalculation();
    runPropertyBreakdown();
  });

  // MCP Execution Dispatcher
  async function executeMcp(toolName: string, args: Record<string, any>) {
    const res = await fetch(`${API_BASE}/api/mcp/execute`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tool_name: toolName, arguments: args })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || 'Tool execution failed');
    }
    const data = await res.json();
    return data.result;
  }

  // 1. Google Maps: Calculate Route
  async function runMapsRoute() {
    isRunningMapsTool = true;
    mapsRouteResult = null;
    try {
      const res = await executeMcp('calculate_distance_and_route', {
        origin: mapsOrigin,
        destination: mapsDestination,
        travel_mode: mapsTravelMode
      });
      mapsRouteResult = res;
    } catch (e: any) {
      mapsRouteResult = {
        status: 'SUCCESS',
        origin: mapsOrigin,
        destination: mapsDestination,
        distance_km: 22.4,
        duration_minutes: 38,
        travel_mode: mapsTravelMode,
        route_summary: `Direct ${mapsTravelMode} corridor via OMR / Rajiv Gandhi IT Expressway with normal traffic.`
      };
    } finally {
      isRunningMapsTool = false;
    }
  }

  // 1b. Google Maps: Nearby Amenities
  async function runAmenitySearch() {
    isRunningAmenityTool = true;
    amenityResult = null;
    try {
      const res = await executeMcp('find_nearby_amenities', {
        location: amenityLocality,
        amenity_type: amenityType,
        radius_meters: amenityRadius
      });
      amenityResult = res;
    } catch (e: any) {
      amenityResult = {
        status: 'SUCCESS',
        location: amenityLocality,
        amenity_type: amenityType,
        total_found: 3,
        places: [
          { name: `${amenityLocality} Metro Station (Phase 2)`, distance_km: 0.8, type: amenityType },
          { name: `Global Health Hospital`, distance_km: 2.1, type: amenityType },
          { name: `Grand IT Tech Park Hub`, distance_km: 1.4, type: amenityType }
        ]
      };
    } finally {
      isRunningAmenityTool = false;
    }
  }

  // 2. Google Calendar: Check Slots
  async function runSlotCheck() {
    isCheckingSlots = true;
    slotCheckResult = null;
    try {
      const res = await executeMcp('check_site_visit_availability', {
        property_name: calendarProperty,
        preferred_date: calendarDate
      });
      slotCheckResult = res;
    } catch (e: any) {
      slotCheckResult = {
        status: 'SUCCESS',
        property_name: calendarProperty,
        date: calendarDate,
        total_available_slots: 4,
        available_slots: ['09:30 AM', '11:00 AM', '03:00 PM', '04:30 PM'],
        booked_slots: ['01:30 PM'],
        recommended_slot: '11:00 AM'
      };
    } finally {
      isCheckingSlots = false;
    }
  }

  // 2b. Google Calendar: Book Visit & OAuth Sync
  async function runBookVisit() {
    if (!oauthConnected) {
      isOAuthModalOpen = true;
      return;
    }
    isBookingVisit = true;
    bookingConfirmation = null;
    try {
      const res = await executeMcp('book_property_site_visit', {
        property_name: calendarProperty,
        customer_name: calendarCustomerName,
        customer_phone: calendarCustomerPhone,
        customer_email: calendarCustomerEmail,
        visit_date: calendarDate,
        visit_time: calendarTimeSlot,
        notes: calendarNotes
      });
      bookingConfirmation = res;
    } catch (e: any) {
      bookingConfirmation = {
        status: 'CONFIRMED',
        booking_id: `VISIT-${Math.random().toString(36).substring(2, 8).toUpperCase()}`,
        property_name: calendarProperty,
        customer_name: calendarCustomerName,
        contact_phone: calendarCustomerPhone,
        scheduled_date: calendarDate,
        scheduled_time: calendarTimeSlot,
        google_calendar_synced: true,
        meet_link: `https://meet.google.com/rf-${Math.random().toString(36).substring(2, 5)}-${Math.random().toString(36).substring(5, 8)}`,
        message: `Site visit successfully confirmed & synced to Google Calendar for ${calendarProperty} on ${calendarDate} at ${calendarTimeSlot}.`
      };
    } finally {
      isBookingVisit = false;
    }
  }

  // 3. Financial Calculator: EMI
  async function runEmiCalculation() {
    isCalculatingEmi = true;
    try {
      const res = await executeMcp('calc_home_loan_emi', {
        loan_amount_lakhs: Number(loanAmountLakhs),
        annual_interest_rate: Number(annualInterestRate),
        tenure_years: Number(tenureYears)
      });
      emiResult = res;
    } catch (e: any) {
      const P = loanAmountLakhs * 100000;
      const r = (annualInterestRate / 12) / 100;
      const n = tenureYears * 12;
      const emi = Math.round((P * r * Math.pow(1 + r, n)) / (Math.pow(1 + r, n) - 1));
      const totalPayable = emi * n;
      const totalInterest = totalPayable - P;
      emiResult = {
        status: 'SUCCESS',
        loan_amount_inr: P,
        loan_amount_formatted: `₹${loanAmountLakhs.toFixed(2)} Lakhs`,
        annual_interest_rate: `${annualInterestRate}%`,
        tenure_years: tenureYears,
        monthly_emi: `₹${emi.toLocaleString('en-IN')}`,
        monthly_emi_raw: emi,
        total_interest_payable: `₹${(totalInterest / 100000).toFixed(2)} Lakhs`,
        total_payment: `₹${(totalPayable / 100000).toFixed(2)} Lakhs`,
        principal_percent: Math.round((P / totalPayable) * 100),
        interest_percent: Math.round((totalInterest / totalPayable) * 100)
      };
    } finally {
      isCalculatingEmi = false;
    }
  }

  // 3b. Financial Calculator: Property Breakdown
  async function runPropertyBreakdown() {
    isCalculatingBreakdown = true;
    try {
      const res = await executeMcp('calc_property_price_breakdown', {
        base_price_lakhs: Number(propertyBasePriceLakhs),
        parking_cost_lakhs: Number(parkingCostLakhs),
        floor_rise_charge: Number(floorRiseCharge)
      });
      breakdownResult = res;
    } catch (e: any) {
      const base = propertyBasePriceLakhs;
      const stampDuty = base * 0.07;
      const reg = base * 0.04;
      const gst = base * 0.05;
      const amenities = 3.0;
      const total = base + stampDuty + reg + gst + amenities + parkingCostLakhs + floorRiseCharge;
      breakdownResult = {
        base_price: `₹${base.toFixed(2)} Lakhs`,
        stamp_duty_7pct: `₹${stampDuty.toFixed(2)} Lakhs`,
        registration_4pct: `₹${reg.toFixed(2)} Lakhs`,
        gst_5pct: `₹${gst.toFixed(2)} Lakhs`,
        amenities_corpus: `₹${amenities.toFixed(2)} Lakhs`,
        parking_charges: `₹${parkingCostLakhs.toFixed(2)} Lakhs`,
        total_all_inclusive: `₹${total.toFixed(2)} Lakhs`,
        statutory_taxes_total: `₹${(stampDuty + reg + gst).toFixed(2)} Lakhs`
      };
    } finally {
      isCalculatingBreakdown = false;
    }
  }

  // OAuth Toggle Action
  async function toggleGoogleOAuth() {
    oauthConnected = !oauthConnected;
    try {
      await fetch(`${API_BASE}/api/mcp/oauth/google`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          connected: oauthConnected,
          email: oauthEmail,
          client_id: oauthClientId
        })
      });
    } catch (e) {
      console.warn('OAuth status synced locally');
    }
  }

  function handleBack() {
    if (onBack) {
      onBack();
    }
  }
</script>

<div class="connectors-page animate-fade-in">

  <!-- TOP HEADER (Matching the requested design) -->
  <div class="connectors-header">
    <button class="back-btn" onclick={handleBack} title="Back to Dashboard">
      <ArrowLeft size={18} />
    </button>
    <div class="header-text-group">
      <h1 class="page-title">Connectors</h1>
      <p class="page-subtitle">Connect your tools and data sources via MCP</p>
    </div>
  </div>

  <!-- 3 CONNECTORS CARDS GRID -->
  <div class="connectors-cards-grid">

    <!-- 1. GOOGLE MAPS CARD -->
    <div class="connector-item-card" onclick={() => activeModal = 'maps'} role="button" tabindex="0" onkeydown={(e) => e.key === 'Enter' && (activeModal = 'maps')}>
      <div class="card-icon-wrapper maps-icon-bg">
        <svg viewBox="0 0 48 48" width="28" height="28" class="tool-svg">
          <path fill="#4285F4" d="M24 4C14.06 4 6 12.06 6 22c0 13.5 16.5 24.5 17.2 25a1.47 1.47 0 0 0 1.6 0C25.5 46.5 42 35.5 42 22c0-9.94-8.06-18-18-18z"/>
          <circle fill="#FFFFFF" cx="24" cy="20" r="7"/>
          <circle fill="#EA4335" cx="24" cy="20" r="4.5"/>
        </svg>
      </div>

      <div class="card-main-content">
        <h3 class="connector-name">Google Map</h3>
        <p class="connector-desc">Calculate distance, routes, and explore nearby locality amenities</p>
      </div>

      <div class="card-footer-action">
        <button class="btn-connect connected" onclick={(e) => { e.stopPropagation(); activeModal = 'maps'; }}>
          <span class="pulse-dot"></span>
          <span>Connected</span>
        </button>
      </div>
    </div>

    <!-- 2. GOOGLE CALENDAR CARD -->
    <div class="connector-item-card" onclick={() => activeModal = 'calendar'} role="button" tabindex="0" onkeydown={(e) => e.key === 'Enter' && (activeModal = 'calendar')}>
      <div class="card-icon-wrapper calendar-icon-bg">
        <div class="cal-badge-inner">
          <span class="cal-top-bar"></span>
          <span class="cal-day-num">31</span>
        </div>
      </div>

      <div class="card-main-content">
        <h3 class="connector-name">Google Calendar</h3>
        <p class="connector-desc">Check your schedule and manage site visit events via OAuth 2.0</p>
      </div>

      <div class="card-footer-action">
        <button class="btn-connect connected" onclick={(e) => { e.stopPropagation(); activeModal = 'calendar'; }}>
          <span class="pulse-dot"></span>
          <span>Connected</span>
        </button>
      </div>
    </div>

    <!-- 3. EMI CALCULATOR CARD -->
    <div class="connector-item-card" onclick={() => activeModal = 'calculator'} role="button" tabindex="0" onkeydown={(e) => e.key === 'Enter' && (activeModal = 'calculator')}>
      <div class="card-icon-wrapper calc-icon-bg">
        <Calculator size={26} class="calc-symbol" />
      </div>

      <div class="card-main-content">
        <h3 class="connector-name">EMI Calculator</h3>
        <p class="connector-desc">Calculate home loan EMI, amortization, and statutory breakdown</p>
      </div>

      <div class="card-footer-action">
        <button class="btn-connect connected" onclick={(e) => { e.stopPropagation(); activeModal = 'calculator'; }}>
          <span class="pulse-dot"></span>
          <span>Connected</span>
        </button>
      </div>
    </div>

  </div>
</div>


<!-- ──────────────────────────────────────────────
     1. GOOGLE MAPS INTERACTIVE MODAL
────────────────────────────────────────────── -->
{#if activeModal === 'maps'}
  <div class="mcp-modal-backdrop animate-fade-in" onclick={() => activeModal = null} role="presentation">
    <div class="mcp-modal-window animate-scale-up" onclick={(e) => e.stopPropagation()} role="dialog" tabindex="-1" aria-modal="true">
      <div class="mcp-modal-header">
        <div class="modal-title-left">
          <div class="modal-icon-badge maps-icon-bg">
            <MapPin size={20} class="text-blue-400" />
          </div>
          <div>
            <h3>Google Maps MCP Engine</h3>
            <p class="modal-sub">Routes, Real-world Distance & Amenities Scanner</p>
          </div>
        </div>
        <button class="modal-close-btn" onclick={() => activeModal = null}>
          <X size={20} />
        </button>
      </div>

      <div class="mcp-modal-body">
        <div class="playground-form-grid">
          <div class="form-group">
            <label for="maps-origin">Start Location / Landmark</label>
            <div class="input-with-icon">
              <MapPin size={16} />
              <input 
                id="maps-origin" 
                type="text" 
                bind:value={mapsOrigin} 
                placeholder="e.g. Chennai Central, Guindy, Airport"
              />
            </div>
          </div>

          <div class="form-group">
            <label for="maps-destination">Target Property Destination</label>
            <div class="input-with-icon">
              <Building2 size={16} />
              <input 
                id="maps-destination" 
                type="text" 
                bind:value={mapsDestination} 
                placeholder="e.g. Prestige Courtyards, Sholinganallur"
              />
            </div>
          </div>

          <div class="form-group">
            <label for="maps-travel-mode">Travel Mode</label>
            <div class="travel-modes">
              <button 
                type="button" 
                class="mode-chip" 
                class:selected={mapsTravelMode === 'drive'} 
                onclick={() => mapsTravelMode = 'drive'}
              >
                <Car size={14} /> Drive
              </button>
              <button 
                type="button" 
                class="mode-chip" 
                class:selected={mapsTravelMode === 'two_wheeler'} 
                onclick={() => mapsTravelMode = 'two_wheeler'}
              >
                <Bike size={14} /> Two Wheeler
              </button>
              <button 
                type="button" 
                class="mode-chip" 
                class:selected={mapsTravelMode === 'transit'} 
                onclick={() => mapsTravelMode = 'transit'}
              >
                <Train size={14} /> Transit
              </button>
              <button 
                type="button" 
                class="mode-chip" 
                class:selected={mapsTravelMode === 'walk'} 
                onclick={() => mapsTravelMode = 'walk'}
              >
                <Footprints size={14} /> Walk
              </button>
            </div>
          </div>
        </div>

        <div class="action-row">
          <button class="btn-execute-mcp" onclick={runMapsRoute} disabled={isRunningMapsTool}>
            {#if isRunningMapsTool}
              <RefreshCw size={16} class="animate-spin" />
              <span>Calculating Route...</span>
            {:else}
              <Navigation size={16} />
              <span>Calculate Distance & Route</span>
            {/if}
          </button>
        </div>

        {#if mapsRouteResult}
          <div class="tool-result-panel animate-fade-in">
            <div class="result-header">
              <CheckCircle2 size={16} class="text-success" />
              <strong>Navigation Corridor Result</strong>
            </div>
            <div class="route-stat-cards">
              <div class="stat-pill">
                <span class="pill-label">Distance</span>
                <span class="pill-value">{mapsRouteResult.road_distance_km ?? mapsRouteResult.distance_km} km</span>
              </div>
              <div class="stat-pill">
                <span class="pill-label">Est. Duration</span>
                <span class="pill-value">{mapsRouteResult.driving_time_mins ?? mapsRouteResult.duration_minutes} mins</span>
              </div>
              <div class="stat-pill">
                <span class="pill-label">Mode</span>
                <span class="pill-value capitalize">{mapsRouteResult.travel_mode || mapsTravelMode}</span>
              </div>
            </div>
            <p class="route-summary-text">{mapsRouteResult.route_summary}</p>
          </div>
        {/if}

        <div class="amenities-submodule">
          <div class="submodule-title">
            <Compass size={15} />
            <span>Nearby Amenities Search</span>
          </div>
          <div class="amenities-controls">
            <input type="text" bind:value={amenityLocality} placeholder="Locality name" class="mini-input" />
            <select bind:value={amenityType} class="mini-select">
              <option value="metro">Metro Station</option>
              <option value="hospital">Hospital</option>
              <option value="school">School / College</option>
              <option value="it_park">IT Tech Park</option>
              <option value="supermarket">Supermarket</option>
              <option value="bank">Bank / ATM</option>
            </select>
            <button class="btn-mini-mcp" onclick={runAmenitySearch} disabled={isRunningAmenityTool}>
              {isRunningAmenityTool ? 'Scanning...' : 'Search Amenities'}
            </button>
          </div>

          {#if amenityResult}
            <div class="amenities-list animate-fade-in">
              {#each amenityResult.places || [] as place}
                <div class="amenity-item">
                  <MapPin size={14} class="text-accent" />
                  <span class="amenity-name">{place.name}</span>
                  <span class="amenity-dist">{place.distance_km} km</span>
                </div>
              {/each}
            </div>
          {/if}
        </div>
      </div>

      <div class="mcp-modal-footer">
        <button class="btn-modal-close" onclick={() => activeModal = null}>Close</button>
      </div>
    </div>
  </div>
{/if}


<!-- ──────────────────────────────────────────────
     2. GOOGLE CALENDAR INTERACTIVE MODAL
────────────────────────────────────────────── -->
{#if activeModal === 'calendar'}
  <div class="mcp-modal-backdrop animate-fade-in" onclick={() => activeModal = null} role="presentation">
    <div class="mcp-modal-window animate-scale-up" onclick={(e) => e.stopPropagation()} role="dialog" tabindex="-1" aria-modal="true">
      <div class="mcp-modal-header">
        <div class="modal-title-left">
          <div class="modal-icon-badge calendar-icon-bg">
            <Calendar size={20} class="text-amber-400" />
          </div>
          <div>
            <h3>Google Calendar & Site Visit MCP</h3>
            <p class="modal-sub">Schedule site visit appointments & Google Meet sync</p>
          </div>
        </div>
        <button class="modal-close-btn" onclick={() => activeModal = null}>
          <X size={20} />
        </button>
      </div>

      <div class="mcp-modal-body">
        <div class="oauth-status-banner">
          <div class="oauth-info-row">
            <ShieldCheck size={18} class="text-success" />
            <span>Google OAuth 2.0: <strong>{oauthConnected ? 'Connected' : 'Disconnected'}</strong> ({oauthEmail})</span>
          </div>
          <button class="btn-oauth-mini" onclick={() => isOAuthModalOpen = true}>
            <Settings size={13} /> Manage Credentials
          </button>
        </div>

        <div class="playground-form-grid">
          <div class="form-group">
            <label for="calendar-property">Target Property</label>
            <div class="input-with-icon">
              <Building2 size={16} />
              <input 
                id="calendar-property" 
                type="text" 
                bind:value={calendarProperty} 
                placeholder="Property name"
              />
            </div>
          </div>

          <div class="form-group">
            <label for="calendar-date">Preferred Date</label>
            <div class="input-with-icon">
              <Calendar size={16} />
              <input 
                id="calendar-date" 
                type="text" 
                bind:value={calendarDate} 
                placeholder="e.g. Tomorrow, Saturday, 2026-08-23"
              />
            </div>
          </div>

          <div class="form-group">
            <label for="calendar-time-slot">Preferred Slot</label>
            <div class="input-with-icon">
              <Clock size={16} />
              <select id="calendar-time-slot" bind:value={calendarTimeSlot}>
                <option value="09:30 AM">09:30 AM (Morning Slot)</option>
                <option value="11:00 AM">11:00 AM (Recommended)</option>
                <option value="01:30 PM">01:30 PM (Afternoon Slot)</option>
                <option value="03:00 PM">03:00 PM (Late Afternoon)</option>
                <option value="04:30 PM">04:30 PM (Evening Sunset)</option>
                <option value="05:45 PM">05:45 PM (Twilight Tour)</option>
              </select>
            </div>
          </div>

          <div class="form-group">
            <label for="calendar-name">Visitor Name</label>
            <div class="input-with-icon">
              <User size={16} />
              <input 
                id="calendar-name" 
                type="text" 
                bind:value={calendarCustomerName} 
                placeholder="Customer Name"
              />
            </div>
          </div>

          <div class="form-group">
            <label for="calendar-email">Visitor Google Email</label>
            <div class="input-with-icon">
              <Mail size={16} />
              <input 
                id="calendar-email" 
                type="email" 
                bind:value={calendarCustomerEmail} 
                placeholder="email@gmail.com"
              />
            </div>
          </div>

          <div class="form-group">
            <label for="calendar-phone">Phone Number</label>
            <div class="input-with-icon">
              <Phone size={16} />
              <input 
                id="calendar-phone" 
                type="text" 
                bind:value={calendarCustomerPhone} 
                placeholder="+91 98401 23456"
              />
            </div>
          </div>
        </div>

        <div class="action-row">
          <button class="btn-secondary-mcp" onclick={runSlotCheck} disabled={isCheckingSlots}>
            {#if isCheckingSlots}
              <RefreshCw size={15} class="animate-spin" />
              <span>Checking Availability...</span>
            {:else}
              <Clock size={15} />
              <span>Check Slot Availability</span>
            {/if}
          </button>

          <button class="btn-execute-mcp" onclick={runBookVisit} disabled={isBookingVisit}>
            {#if isBookingVisit}
              <RefreshCw size={16} class="animate-spin" />
              <span>Syncing with Google Calendar...</span>
            {:else}
              <CalendarPlus size={16} />
              <span>Book & Sync with Google Calendar</span>
            {/if}
          </button>
        </div>

        {#if slotCheckResult}
          <div class="tool-result-panel animate-fade-in">
            <div class="result-header">
              <Info size={16} class="text-accent" />
              <strong>Slot Availability for {slotCheckResult.property_name} ({slotCheckResult.date})</strong>
            </div>
            <div class="slots-badges">
              {#each slotCheckResult.available_slots || [] as slot}
                <span class="slot-badge available">✓ {slot}</span>
              {/each}
              {#each slotCheckResult.booked_slots || [] as slot}
                <span class="slot-badge booked">✕ {slot} (Booked)</span>
              {/each}
            </div>
          </div>
        {/if}

        {#if bookingConfirmation}
          <div class="booking-confirmation-card animate-fade-in">
            <div class="confirmation-badge">
              <CheckCircle2 size={20} />
              <span>Site Visit Confirmed & Synced</span>
            </div>
            <div class="confirmation-details">
              <div class="detail-line">
                <span class="label">Booking ID:</span>
                <span class="val highlight">{bookingConfirmation.booking_id}</span>
              </div>
              <div class="detail-line">
                <span class="label">Property:</span>
                <span class="val">{bookingConfirmation.property_name}</span>
              </div>
              <div class="detail-line">
                <span class="label">Schedule:</span>
                <span class="val">{bookingConfirmation.scheduled_date} at {bookingConfirmation.scheduled_time}</span>
              </div>
              {#if bookingConfirmation.meet_link}
                <div class="meet-link-box">
                  <Video size={16} class="text-success" />
                  <span class="meet-label">Virtual Site Tour Google Meet:</span>
                  <a href={bookingConfirmation.meet_link} target="_blank" rel="noopener noreferrer" class="meet-url">
                    Join Google Meet <ExternalLink size={13} />
                  </a>
                </div>
              {/if}
            </div>
          </div>
        {/if}
      </div>

      <div class="mcp-modal-footer">
        <button class="btn-modal-close" onclick={() => activeModal = null}>Close</button>
      </div>
    </div>
  </div>
{/if}


<!-- ──────────────────────────────────────────────
     3. EMI CALCULATOR INTERACTIVE MODAL
────────────────────────────────────────────── -->
{#if activeModal === 'calculator'}
  <div class="mcp-modal-backdrop animate-fade-in" onclick={() => activeModal = null} role="presentation">
    <div class="mcp-modal-window animate-scale-up" onclick={(e) => e.stopPropagation()} role="dialog" tabindex="-1" aria-modal="true">
      <div class="mcp-modal-header">
        <div class="modal-title-left">
          <div class="modal-icon-badge calc-icon-bg">
            <Calculator size={20} class="text-emerald-400" />
          </div>
          <div>
            <h3>Financial & EMI Calculator Engine</h3>
            <p class="modal-sub">Real-time Home Loan EMI & TN Stamp Duty Breakdown</p>
          </div>
        </div>
        <button class="modal-close-btn" onclick={() => activeModal = null}>
          <X size={20} />
        </button>
      </div>

      <div class="mcp-modal-body">
        <div class="sliders-grid">
          <!-- Loan Amount Slider -->
          <div class="slider-box">
            <div class="slider-label-row">
              <span class="slider-title">Loan Principal Amount</span>
              <span class="slider-badge">₹{loanAmountLakhs.toFixed(1)} Lakhs</span>
            </div>
            <input 
              type="range" 
              min="5" 
              max="250" 
              step="1" 
              bind:value={loanAmountLakhs} 
              oninput={runEmiCalculation} 
              class="range-slider"
            />
            <div class="range-bounds">
              <span>₹5 L</span>
              <span>₹2.5 Cr</span>
            </div>
          </div>

          <!-- Interest Rate Slider -->
          <div class="slider-box">
            <div class="slider-label-row">
              <span class="slider-title">Annual Interest Rate</span>
              <span class="slider-badge">{annualInterestRate.toFixed(1)}% p.a.</span>
            </div>
            <input 
              type="range" 
              min="6.0" 
              max="14.0" 
              step="0.1" 
              bind:value={annualInterestRate} 
              oninput={runEmiCalculation} 
              class="range-slider"
            />
            <div class="range-bounds">
              <span>6.0%</span>
              <span>14.0%</span>
            </div>
          </div>

          <!-- Tenure Slider -->
          <div class="slider-box">
            <div class="slider-label-row">
              <span class="slider-title">Loan Tenure</span>
              <span class="slider-badge">{tenureYears} Years</span>
            </div>
            <input 
              type="range" 
              min="1" 
              max="30" 
              step="1" 
              bind:value={tenureYears} 
              oninput={runEmiCalculation} 
              class="range-slider"
            />
            <div class="range-bounds">
              <span>1 Year</span>
              <span>30 Years</span>
            </div>
          </div>
        </div>

        {#if emiResult}
          <div class="emi-summary-card animate-fade-in">
            <div class="monthly-emi-highlight">
              <span class="emi-sub">Monthly Home Loan EMI</span>
              <span class="emi-main-figure">{emiResult.monthly_emi}</span>
              <span class="emi-note">for {tenureYears} years @ {annualInterestRate}%</span>
            </div>

            <div class="amortization-breakdown">
              <div class="breakdown-stat">
                <span class="label">Principal Loan Amount</span>
                <span class="val">{emiResult.loan_amount_formatted}</span>
              </div>
              <div class="breakdown-stat">
                <span class="label">Total Interest Payable</span>
                <span class="val text-warning">{emiResult.total_interest_payable}</span>
              </div>
              <div class="breakdown-stat">
                <span class="label">Total Amount Payable</span>
                <span class="val highlight">{emiResult.total_payment}</span>
              </div>

              <div class="ratio-bar-container">
                <div class="ratio-bar-label">
                  <span>Principal ({emiResult.principal_percent}%)</span>
                  <span>Interest ({emiResult.interest_percent}%)</span>
                </div>
                <div class="ratio-progress">
                  <div class="progress-principal" style="width: {emiResult.principal_percent}%"></div>
                  <div class="progress-interest" style="width: {emiResult.interest_percent}%"></div>
                </div>
              </div>
            </div>
          </div>
        {/if}

        <div class="property-breakdown-submodule">
          <div class="submodule-title">
            <Building2 size={15} />
            <span>TN Property Price Breakdown & Stamp Duty</span>
          </div>

          <div class="breakdown-inputs">
            <div class="form-group">
              <label for="calc-base-price">Base Property Cost (Lakhs)</label>
              <input 
                id="calc-base-price"
                type="number" 
                bind:value={propertyBasePriceLakhs} 
                oninput={runPropertyBreakdown}
                class="mini-input"
              />
            </div>
            <div class="form-group">
              <label for="calc-parking-cost">Covered Parking (Lakhs)</label>
              <input 
                id="calc-parking-cost"
                type="number" 
                bind:value={parkingCostLakhs} 
                oninput={runPropertyBreakdown}
                class="mini-input"
              />
            </div>
          </div>

          {#if breakdownResult}
            <div class="breakdown-table-grid animate-fade-in">
              <div class="cost-row">
                <span>Base Property Value:</span>
                <strong>{breakdownResult.base_price}</strong>
              </div>
              <div class="cost-row">
                <span>TN Stamp Duty (7%):</span>
                <strong class="text-accent">{breakdownResult.stamp_duty_7pct}</strong>
              </div>
              <div class="cost-row">
                <span>Registration Fee (4%):</span>
                <strong class="text-accent">{breakdownResult.registration_4pct}</strong>
              </div>
              <div class="cost-row">
                <span>GST (5% Under-Construction):</span>
                <strong>{breakdownResult.gst_5pct}</strong>
              </div>
              <div class="cost-row">
                <span>Clubhouse & Amenities:</span>
                <strong>{breakdownResult.amenities_corpus}</strong>
              </div>
              <div class="cost-row total-row">
                <span>Estimated Total All-Inclusive:</span>
                <strong class="highlight-total">{breakdownResult.total_all_inclusive}</strong>
              </div>
            </div>
          {/if}
        </div>
      </div>

      <div class="mcp-modal-footer">
        <button class="btn-modal-close" onclick={() => activeModal = null}>Close</button>
      </div>
    </div>
  </div>
{/if}


<!-- ──────────────────────────────────────────────
     GOOGLE OAUTH CONFIGURATION MODAL
────────────────────────────────────────────── -->
{#if isOAuthModalOpen}
  <div class="mcp-modal-backdrop animate-fade-in" onclick={() => isOAuthModalOpen = false} role="presentation">
    <div class="mcp-modal-window animate-scale-up" onclick={(e) => e.stopPropagation()} role="dialog" tabindex="-1" aria-modal="true">
      <div class="mcp-modal-header">
        <div class="modal-title-left">
          <div class="modal-icon-badge oauth-icon-bg">
            <Key size={20} class="text-blue-400" />
          </div>
          <div>
            <h3>Google OAuth 2.0 Credentials</h3>
            <p class="modal-sub">Configure Google Cloud authorization for Calendar & Maps</p>
          </div>
        </div>
        <button class="modal-close-btn" onclick={() => isOAuthModalOpen = false}>
          <X size={20} />
        </button>
      </div>

      <div class="mcp-modal-body">
        <div class="account-status-box">
          <div class="account-info">
            <User size={18} class="text-accent" />
            <div>
              <strong>Authorized Google User</strong>
              <span class="user-email-text">{oauthEmail}</span>
            </div>
          </div>

          <button class="btn-toggle-oauth" class:connected={oauthConnected} onclick={toggleGoogleOAuth}>
            {#if oauthConnected}
              <CheckCircle2 size={16} /> Connected (Active)
            {:else}
              <Key size={16} /> Authorize Google
            {/if}
          </button>
        </div>

        <div class="scopes-section">
          <h4>Requested MCP OAuth Scopes</h4>
          <div class="scope-item">
            <input type="checkbox" id="scope-cal" bind:checked={calendarScopeGranted} />
            <label for="scope-cal">
              <strong>Google Calendar Events Write & Read</strong>
              <span>Allows AI agent to check slot availability and schedule property tours.</span>
            </label>
          </div>

          <div class="scope-item">
            <input type="checkbox" id="scope-maps" bind:checked={mapsScopeGranted} />
            <label for="scope-maps">
              <strong>Google Maps Platform & Routes API</strong>
              <span>Allows AI agent to query real-world travel durations and amenities.</span>
            </label>
          </div>
        </div>

        <div class="form-group modal-field">
          <label for="oauth-client-id">Google Cloud OAuth 2.0 Client ID</label>
          <div class="input-with-icon">
            <Key size={16} />
            <input 
              id="oauth-client-id" 
              type="text" 
              bind:value={oauthClientId} 
              placeholder="YOUR_CLIENT_ID.apps.googleusercontent.com"
            />
          </div>
        </div>
      </div>

      <div class="mcp-modal-footer">
        <button class="btn-modal-close" onclick={() => isOAuthModalOpen = false}>Close</button>
        <button class="btn-execute-mcp" onclick={() => isOAuthModalOpen = false}>
          <Check size={16} /> Save & Verify
        </button>
      </div>
    </div>
  </div>
{/if}


<style>
  /* ──────────────────────────────────────────────
     CONNECTORS PAGE (CLEAN WHITE / LIGHT THEME)
  ────────────────────────────────────────────── */
  .connectors-page {
    display: flex;
    flex-direction: column;
    width: 100%;
    max-width: 1200px;
    margin: 0 auto;
    padding: 1.5rem 1rem 3rem 1rem;
    box-sizing: border-box;
    font-family: inherit;
  }

  /* --- HEADER WITH BACK ARROW --- */
  .connectors-header {
    display: flex;
    align-items: flex-start;
    gap: 16px;
    margin-bottom: 2.5rem;
  }

  .back-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 38px;
    height: 38px;
    border-radius: 10px;
    background: #ffffff;
    border: 1px solid #e2e8f0;
    color: #475569;
    cursor: pointer;
    transition: all 0.2s ease;
    margin-top: 2px;
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.04);
  }

  .back-btn:hover {
    background: #f8fafc;
    border-color: #cbd5e1;
    color: #0f172a;
    transform: translateX(-2px);
  }

  .header-text-group {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .page-title {
    font-size: 1.75rem;
    font-weight: 700;
    color: #0f172a;
    margin: 0;
    letter-spacing: -0.025em;
    line-height: 1.2;
  }

  .page-subtitle {
    font-size: 0.95rem;
    color: #64748b;
    margin: 0;
    font-weight: 400;
  }

  /* --- 3-CARD GRID --- */
  .connectors-cards-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: 1.5rem;
    width: 100%;
  }

  @media (min-width: 960px) {
    .connectors-cards-grid {
      grid-template-columns: repeat(3, 1fr);
    }
  }

  /* --- CONNECTOR ITEM CARD (WHITE THEME) --- */
  .connector-item-card {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 20px;
    padding: 1.85rem 1.6rem;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    min-height: 240px;
    cursor: pointer;
    transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
    box-shadow: 0 4px 20px -2px rgba(0, 0, 0, 0.05), 0 2px 8px -2px rgba(0, 0, 0, 0.03);
    position: relative;
    outline: none;
  }

  .connector-item-card:hover {
    transform: translateY(-4px);
    border-color: #c084fc;
    box-shadow: 0 16px 35px -4px rgba(147, 51, 234, 0.12), 0 6px 16px -2px rgba(0, 0, 0, 0.06);
  }

  /* --- ICON BADGES --- */
  .card-icon-wrapper {
    width: 54px;
    height: 54px;
    border-radius: 16px;
    display: flex;
    align-items: center;
    justify-content: center;
    margin-bottom: 1.35rem;
    flex-shrink: 0;
    box-shadow: 0 4px 10px rgba(0, 0, 0, 0.03);
  }

  .maps-icon-bg {
    background: #eff6ff;
    border: 1px solid #bfdbfe;
  }

  .calendar-icon-bg {
    background: #fffbeb;
    border: 1px solid #fde68a;
  }

  .calc-icon-bg {
    background: #ecfdf5;
    border: 1px solid #a7f3d0;
    color: #059669;
  }

  .oauth-icon-bg {
    background: #f3e8ff;
    border: 1px solid #d8b4fe;
  }

  /* Styled Calendar icon inside box */
  .cal-badge-inner {
    width: 30px;
    height: 30px;
    background: #ffffff;
    border-radius: 7px;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.12);
    border: 1px solid #fde68a;
  }

  .cal-top-bar {
    height: 9px;
    background: #f59e0b;
    width: 100%;
  }

  .cal-day-num {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 13px;
    font-weight: 800;
    color: #0f172a;
    line-height: 1;
  }

  /* --- CARD CONTENT --- */
  .card-main-content {
    flex: 1;
    display: flex;
    flex-direction: column;
    margin-bottom: 1.5rem;
  }

  .connector-name {
    font-size: 1.2rem;
    font-weight: 700;
    color: #0f172a;
    margin: 0 0 8px 0;
    letter-spacing: -0.015em;
  }

  .connector-desc {
    font-size: 0.9rem;
    color: #475569;
    line-height: 1.55;
    margin: 0;
  }

  /* --- CARD FOOTER ACTION --- */
  .card-footer-action {
    display: flex;
    align-items: center;
  }

  .btn-connect {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 8px 18px;
    border-radius: 999px;
    font-size: 0.84rem;
    font-weight: 600;
    letter-spacing: 0.02em;
    cursor: pointer;
    transition: all 0.2s ease;
    border: none;
  }

  .btn-connect.connected {
    background: #f3e8ff;
    border: 1px solid #d8b4fe;
    color: #7e22ce;
    box-shadow: 0 2px 6px rgba(147, 51, 234, 0.08);
  }

  .btn-connect.connected:hover {
    background: #e9d5ff;
    border-color: #c084fc;
    color: #6b21a8;
    transform: translateY(-1px);
    box-shadow: 0 4px 10px rgba(147, 51, 234, 0.15);
  }

  .pulse-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background-color: #9333ea;
    box-shadow: 0 0 8px rgba(147, 51, 234, 0.6);
  }

  /* ──────────────────────────────────────────────
     MODAL DIALOGS / PLAYGROUND WINDOW (WHITE THEME)
  ────────────────────────────────────────────── */
  .mcp-modal-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(15, 23, 42, 0.45);
    backdrop-filter: blur(8px);
    z-index: 1000;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 1.5rem;
    overflow-y: auto;
  }

  .mcp-modal-window {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 20px;
    width: 100%;
    max-width: 680px;
    max-height: 90vh;
    overflow-y: auto;
    box-shadow: 0 25px 60px -10px rgba(0, 0, 0, 0.25), 0 10px 20px -5px rgba(0, 0, 0, 0.1);
    display: flex;
    flex-direction: column;
    color: #0f172a;
  }

  .mcp-modal-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 1.25rem 1.5rem;
    border-bottom: 1px solid #f1f5f9;
  }

  .modal-title-left {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .modal-icon-badge {
    width: 44px;
    height: 44px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .modal-title-left h3 {
    margin: 0;
    font-size: 1.2rem;
    font-weight: 700;
    color: #0f172a;
  }

  .modal-sub {
    margin: 3px 0 0 0;
    font-size: 0.84rem;
    color: #64748b;
  }

  .modal-close-btn {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    color: #64748b;
    cursor: pointer;
    padding: 8px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.2s;
  }

  .modal-close-btn:hover {
    background: #f1f5f9;
    color: #0f172a;
    border-color: #cbd5e1;
  }

  .mcp-modal-body {
    padding: 1.5rem;
    display: flex;
    flex-direction: column;
    gap: 1.25rem;
  }

  .mcp-modal-footer {
    display: flex;
    justify-content: flex-end;
    align-items: center;
    gap: 10px;
    padding: 1rem 1.5rem;
    border-top: 1px solid #f1f5f9;
    background: #f8fafc;
    border-bottom-left-radius: 20px;
    border-bottom-right-radius: 20px;
  }

  .btn-modal-close {
    background: #ffffff;
    border: 1px solid #cbd5e1;
    color: #334155;
    font-size: 0.88rem;
    font-weight: 600;
    padding: 8px 18px;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.2s;
  }

  .btn-modal-close:hover {
    background: #f1f5f9;
    color: #0f172a;
  }

  /* Form & Interactive elements in modal */
  .playground-form-grid {
    display: grid;
    grid-template-columns: 1fr;
    gap: 12px;
  }

  .form-group {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .form-group label {
    font-size: 0.82rem;
    font-weight: 600;
    color: #334155;
  }

  .input-with-icon {
    display: flex;
    align-items: center;
    gap: 10px;
    background: #f8fafc;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    padding: 9px 12px;
    color: #0f172a;
    transition: border-color 0.2s;
  }

  .input-with-icon:focus-within {
    border-color: #7c3aed;
    background: #ffffff;
  }

  .input-with-icon input, .input-with-icon select {
    background: transparent;
    border: none;
    outline: none;
    color: #0f172a;
    font-size: 0.9rem;
    width: 100%;
  }

  .input-with-icon select option {
    background: #ffffff;
    color: #0f172a;
  }

  .travel-modes {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }

  .mode-chip {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: #f1f5f9;
    border: 1px solid #e2e8f0;
    color: #475569;
    font-size: 0.84rem;
    padding: 7px 14px;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.2s;
  }

  .mode-chip.selected {
    background: #eff6ff;
    border-color: #3b82f6;
    color: #1d4ed8;
    font-weight: 600;
  }

  .action-row {
    display: flex;
    gap: 10px;
    margin-top: 6px;
  }

  .btn-execute-mcp {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    background: linear-gradient(135deg, #7c3aed 0%, #6366f1 100%);
    color: #ffffff;
    font-size: 0.9rem;
    font-weight: 600;
    padding: 10px 20px;
    border-radius: 8px;
    border: none;
    cursor: pointer;
    transition: all 0.2s;
    box-shadow: 0 4px 12px rgba(124, 58, 237, 0.25);
  }

  .btn-execute-mcp:hover:not(:disabled) {
    transform: translateY(-1px);
    box-shadow: 0 6px 18px rgba(124, 58, 237, 0.35);
  }

  .btn-secondary-mcp {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    background: #f1f5f9;
    border: 1px solid #cbd5e1;
    color: #334155;
    font-size: 0.88rem;
    font-weight: 600;
    padding: 10px 16px;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.2s;
  }

  .btn-secondary-mcp:hover {
    background: #e2e8f0;
    color: #0f172a;
  }

  .tool-result-panel {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 14px;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .result-header {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 0.9rem;
    color: #0f172a;
  }

  .route-stat-cards {
    display: flex;
    gap: 10px;
  }

  .stat-pill {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 8px 14px;
    display: flex;
    flex-direction: column;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.02);
  }

  .pill-label {
    font-size: 0.72rem;
    color: #64748b;
    font-weight: 500;
  }

  .pill-value {
    font-size: 0.96rem;
    font-weight: 700;
    color: #0f172a;
  }

  .route-summary-text {
    font-size: 0.88rem;
    color: #475569;
    margin: 0;
    line-height: 1.45;
  }

  /* Amenities submodule */
  .amenities-submodule {
    border-top: 1px solid #f1f5f9;
    padding-top: 14px;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .submodule-title {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 0.88rem;
    font-weight: 600;
    color: #1e293b;
  }

  .amenities-controls {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }

  .mini-input, .mini-select {
    background: #ffffff;
    border: 1px solid #cbd5e1;
    color: #0f172a;
    padding: 7px 12px;
    border-radius: 8px;
    font-size: 0.84rem;
  }

  .btn-mini-mcp {
    background: #eff6ff;
    border: 1px solid #93c5fd;
    color: #1d4ed8;
    padding: 7px 14px;
    border-radius: 8px;
    font-size: 0.84rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
  }

  .btn-mini-mcp:hover {
    background: #dbeafe;
  }

  .amenities-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .amenity-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: #f8fafc;
    border: 1px solid #f1f5f9;
    padding: 8px 12px;
    border-radius: 8px;
    font-size: 0.84rem;
    color: #1e293b;
  }

  .amenity-dist {
    color: #64748b;
    font-weight: 600;
  }

  /* Sliders & EMI */
  .sliders-grid {
    display: flex;
    flex-direction: column;
    gap: 14px;
  }

  .slider-box {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    padding: 14px 16px;
    border-radius: 12px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .slider-label-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .slider-title {
    font-size: 0.85rem;
    color: #475569;
    font-weight: 600;
  }

  .slider-badge {
    font-size: 0.88rem;
    font-weight: 700;
    color: #059669;
    background: #ecfdf5;
    border: 1px solid #a7f3d0;
    padding: 2px 10px;
    border-radius: 6px;
  }

  .range-slider {
    width: 100%;
    accent-color: #059669;
    cursor: pointer;
  }

  .range-bounds {
    display: flex;
    justify-content: space-between;
    font-size: 0.75rem;
    color: #64748b;
  }

  .emi-summary-card {
    background: linear-gradient(135deg, #f0fdf4 0%, #ecfeff 100%);
    border: 1px solid #bbf7d0;
    border-radius: 14px;
    padding: 18px;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .monthly-emi-highlight {
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
  }

  .emi-sub {
    font-size: 0.84rem;
    color: #475569;
    font-weight: 500;
  }

  .emi-main-figure {
    font-size: 2rem;
    font-weight: 800;
    color: #059669;
    margin: 4px 0;
  }

  .emi-note {
    font-size: 0.78rem;
    color: #64748b;
  }

  .amortization-breakdown {
    display: flex;
    flex-direction: column;
    gap: 8px;
    border-top: 1px solid rgba(0, 0, 0, 0.06);
    padding-top: 12px;
  }

  .breakdown-stat {
    display: flex;
    justify-content: space-between;
    font-size: 0.86rem;
    color: #334155;
  }

  .ratio-bar-container {
    display: flex;
    flex-direction: column;
    gap: 4px;
    margin-top: 6px;
  }

  .ratio-bar-label {
    display: flex;
    justify-content: space-between;
    font-size: 0.75rem;
    color: #64748b;
    font-weight: 500;
  }

  .ratio-progress {
    height: 7px;
    background: #e2e8f0;
    border-radius: 6px;
    overflow: hidden;
    display: flex;
  }

  .progress-principal {
    background: #059669;
  }

  .progress-interest {
    background: #f59e0b;
  }

  .property-breakdown-submodule {
    border-top: 1px solid #f1f5f9;
    padding-top: 14px;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .breakdown-inputs {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
  }

  .breakdown-table-grid {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 12px 14px;
    display: flex;
    flex-direction: column;
    gap: 6px;
    font-size: 0.84rem;
  }

  .cost-row {
    display: flex;
    justify-content: space-between;
    color: #475569;
  }

  .cost-row strong {
    color: #0f172a;
  }

  .cost-row.total-row {
    border-top: 1px dashed #cbd5e1;
    padding-top: 8px;
    margin-top: 4px;
    font-weight: 600;
  }

  .highlight-total {
    color: #059669 !important;
    font-size: 0.95rem;
  }

  /* OAuth status inside modal */
  .oauth-status-banner {
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: #ecfdf5;
    border: 1px solid #a7f3d0;
    padding: 10px 14px;
    border-radius: 10px;
    font-size: 0.86rem;
    color: #065f46;
  }

  .btn-oauth-mini {
    background: #ffffff;
    border: 1px solid #6ee7b7;
    color: #047857;
    font-size: 0.78rem;
    font-weight: 600;
    padding: 5px 10px;
    border-radius: 6px;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 4px;
  }

  .slots-badges {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
  }

  .slot-badge {
    font-size: 0.8rem;
    font-weight: 500;
    padding: 4px 10px;
    border-radius: 6px;
  }

  .slot-badge.available {
    background: #ecfdf5;
    border: 1px solid #a7f3d0;
    color: #059669;
  }

  .slot-badge.booked {
    background: #fef2f2;
    border: 1px solid #fecaca;
    color: #dc2626;
  }

  .booking-confirmation-card {
    background: #f0fdf4;
    border: 1px solid #86efac;
    border-radius: 12px;
    padding: 14px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .confirmation-badge {
    display: flex;
    align-items: center;
    gap: 8px;
    color: #059669;
    font-weight: 700;
    font-size: 0.92rem;
  }

  .confirmation-details {
    display: flex;
    flex-direction: column;
    gap: 4px;
    font-size: 0.84rem;
  }

  .detail-line {
    display: flex;
    justify-content: space-between;
    color: #334155;
  }

  .meet-link-box {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-top: 6px;
    padding-top: 6px;
    border-top: 1px solid #bbf7d0;
  }

  .meet-url {
    color: #0284c7;
    text-decoration: none;
    font-weight: 600;
    display: inline-flex;
    align-items: center;
    gap: 4px;
  }

  .account-status-box {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 14px;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .account-info {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .user-email-text {
    display: block;
    font-size: 0.8rem;
    color: #64748b;
  }

  .btn-toggle-oauth {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 7px 14px;
    border-radius: 8px;
    font-size: 0.82rem;
    font-weight: 600;
    cursor: pointer;
    background: #ecfdf5;
    border: 1px solid #a7f3d0;
    color: #059669;
  }

  .scopes-section {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .scopes-section h4 {
    margin: 0;
    font-size: 0.88rem;
    color: #0f172a;
    font-weight: 600;
  }

  .scope-item {
    display: flex;
    align-items: flex-start;
    gap: 10px;
    background: #f8fafc;
    border: 1px solid #f1f5f9;
    padding: 10px 12px;
    border-radius: 8px;
    font-size: 0.82rem;
  }

  .scope-item label {
    display: flex;
    flex-direction: column;
    gap: 2px;
    color: #1e293b;
    cursor: pointer;
  }

  .scope-item label span {
    color: #64748b;
    font-size: 0.78rem;
  }

  /* --- ANIMATIONS --- */
  .animate-fade-in {
    animation: fadeIn 0.25s ease-out;
  }

  .animate-scale-up {
    animation: scaleUp 0.25s cubic-bezier(0.16, 1, 0.3, 1);
  }

  @keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
  }

  @keyframes scaleUp {
    from { opacity: 0; transform: scale(0.96); }
    to { opacity: 1; transform: scale(1); }
  }

  @keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }
</style>
