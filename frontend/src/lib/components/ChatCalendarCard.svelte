<script lang="ts">
  import {
    Calendar,
    CalendarCheck,
    Clock,
    MapPin,
    User,
    Phone,
    Video,
    ExternalLink,
    CheckCircle2
  } from '@lucide/svelte';

  interface Props {
    propertyName?: string;
    visitDate?: string;
    visitTime?: string;
    customerName?: string;
    bookingId?: string;
    notes?: string;
  }

  let {
    propertyName = 'Prestige Courtyards, Sholinganallur',
    visitDate = 'Upcoming Saturday',
    visitTime = '11:00 AM',
    customerName = 'Prospective Buyer',
    bookingId = 'VISIT-7A9B2F',
    notes = 'Site Visit & Property Tour'
  }: Props = $props();

  // Compute direct Add to Google Calendar link
  let gcalUrl = $derived.by(() => {
    const title = encodeURIComponent(`Property Site Visit: ${propertyName}`);
    const details = encodeURIComponent(
      `Confirmed Site Visit for ${customerName}.\nBooking Reference ID: ${bookingId}\nNotes: ${notes}\n\nManaged via Real Estate AI Assistant (Google Calendar MCP Connector)`
    );
    const location = encodeURIComponent(`${propertyName}, Chennai, Tamil Nadu`);
    return `https://calendar.google.com/calendar/render?action=TEMPLATE&text=${title}&details=${details}&location=${location}`;
  });
</script>

<div class="calendar-event-card animate-fade-in">
  <div class="card-header">
    <div class="brand-group">
      <div class="calendar-icon-box">
        <Calendar size={18} />
      </div>
      <div>
        <h4 class="event-title">Property Site Visit Scheduled</h4>
        <span class="mcp-sync-badge">
          <span class="live-dot"></span>
          Google Calendar Active (MCP)
        </span>
      </div>
    </div>
    <span class="booking-ref-badge">ID: {bookingId}</span>
  </div>

  <div class="card-body">
    <div class="event-detail-row">
      <div class="detail-icon"><MapPin size={15} /></div>
      <div class="detail-content">
        <span class="detail-label">Location / Property</span>
        <strong class="detail-val">{propertyName}</strong>
      </div>
    </div>

    <div class="event-grid-row">
      <div class="event-detail-row">
        <div class="detail-icon"><Clock size={15} /></div>
        <div class="detail-content">
          <span class="detail-label">Date & Time</span>
          <strong class="detail-val highlight">{visitDate} • {visitTime}</strong>
        </div>
      </div>

      <div class="event-detail-row">
        <div class="detail-icon"><User size={15} /></div>
        <div class="detail-content">
          <span class="detail-label">Client Name</span>
          <strong class="detail-val">{customerName}</strong>
        </div>
      </div>
    </div>
  </div>

  <div class="card-footer">
    <div class="status-note">
      <CheckCircle2 size={14} class="text-success" />
      <span>Appointment confirmed in database</span>
    </div>

    <a 
      href={gcalUrl} 
      target="_blank" 
      rel="noopener noreferrer" 
      class="btn-add-gcal"
    >
      <CalendarCheck size={15} />
      <span>Add to Google Calendar</span>
      <ExternalLink size={13} />
    </a>
  </div>
</div>

<style>
  .calendar-event-card {
    margin: 12px 0 8px 0;
    background: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 16px;
    overflow: hidden;
    box-shadow: 0 4px 20px -2px rgba(0, 0, 0, 0.08);
    max-width: 600px;
    width: 100%;
  }

  .card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 16px;
    background: #f8fafc;
    border-bottom: 1px solid #e2e8f0;
    gap: 12px;
    flex-wrap: wrap;
  }

  .brand-group {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .calendar-icon-box {
    width: 36px;
    height: 36px;
    border-radius: 10px;
    background: linear-gradient(135deg, #059669 0%, #10b981 100%);
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    box-shadow: 0 2px 8px rgba(16, 185, 129, 0.3);
  }

  .event-title {
    font-size: 0.92rem;
    font-weight: 700;
    color: #0f172a;
    margin: 0;
  }

  .mcp-sync-badge {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    background: #ecfdf5;
    color: #059669;
    border: 1px solid #a7f3d0;
    padding: 1px 7px;
    border-radius: 999px;
    font-size: 0.7rem;
    font-weight: 600;
    margin-top: 2px;
  }

  .live-dot {
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: #10b981;
  }

  .booking-ref-badge {
    font-size: 0.72rem;
    padding: 3px 8px;
    border-radius: 6px;
    background: #f1f5f9;
    border: 1px solid #e2e8f0;
    color: #64748b;
    font-family: monospace;
    font-weight: 600;
  }

  .card-body {
    padding: 14px 16px;
    display: flex;
    flex-direction: column;
    gap: 10px;
    background: #ffffff;
  }

  .event-grid-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
  }

  @media (max-width: 500px) {
    .event-grid-row {
      grid-template-columns: 1fr;
    }
  }

  .event-detail-row {
    display: flex;
    align-items: flex-start;
    gap: 10px;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    padding: 8px 12px;
    border-radius: 8px;
  }

  .detail-icon {
    color: #059669;
    margin-top: 2px;
  }

  .detail-content {
    display: flex;
    flex-direction: column;
    gap: 1px;
  }

  .detail-label {
    font-size: 0.7rem;
    color: #64748b;
    text-transform: uppercase;
    font-weight: 600;
  }

  .detail-val {
    font-size: 0.85rem;
    color: #0f172a;
    font-weight: 600;
  }

  .detail-val.highlight {
    color: #059669;
    font-weight: 700;
  }

  .card-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 16px;
    background: #f8fafc;
    border-top: 1px solid #e2e8f0;
    gap: 12px;
    flex-wrap: wrap;
  }

  .status-note {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 0.78rem;
    color: #475569;
  }

  .btn-add-gcal {
    display: inline-flex;
    align-items: center;
    gap: 6px;
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

  .btn-add-gcal:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 14px rgba(16, 185, 129, 0.45);
  }

  .animate-fade-in {
    animation: fadeIn 0.3s ease forwards;
  }

  @keyframes fadeIn {
    from { opacity: 0; transform: translateY(4px); }
    to { opacity: 1; transform: translateY(0); }
  }
</style>
