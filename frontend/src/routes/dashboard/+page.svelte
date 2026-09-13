<script lang="ts">
  import { onMount } from 'svelte';
  import AuthHeader from '$lib/components/AuthHeader.svelte';
  import ChatRouteMap from '$lib/components/ChatRouteMap.svelte';
  import ChatCalendarCard from '$lib/components/ChatCalendarCard.svelte';
  import ConnectorsView from '$lib/components/ConnectorsView.svelte';
  import { authState, verifyWithBackend } from '$lib/auth.svelte';
  import { initClerk } from '$lib/clerk';
  import { goto } from '$app/navigation';
  import { 
    LayoutDashboard, 
    History, 
    Plug,
    Mic, 
    Database, 
    HelpCircle, 
    ChevronLeft, 
    ChevronRight, 
    Sun, 
    Moon, 
    Settings, 
    User, 
    Paperclip, 
    Sparkles, 
    Send, 
    CloudUpload, 
    CheckCircle2, 
    AlertCircle, 
    X, 
    Activity,
    FileText,
    Copy,
    Check,
    ArrowUpRight,
    Search,
    Building2,
    Menu,
    Lock
  } from '@lucide/svelte';

  // --- STATE VARIABLES ---
  
  // Auth Protection Guard
  let authChecking = $state(true);
  let isAccessAllowed = $state(false);
  
  // Navigation & Theme
  let sidebarCollapsed = $state(false);
  let mobileMenuOpen = $state(false);
  let activeSidebarTab = $state('Dashboard'); // 'Dashboard', 'Query History', 'Audio Transcripts', 'Data Sources', 'Help Center'
  let isLightTheme = $state(false);

  // Backend Interaction
  let quickAskQuestion = $state('');
  let isAsking = $state(false);
  let isTranscribing = $state(false);
  
  let textareaRef = $state<HTMLTextAreaElement | null>(null);

  $effect(() => {
    if (quickAskQuestion !== undefined && textareaRef) {
      textareaRef.style.height = '38px';
      if (quickAskQuestion.trim().length > 0 && textareaRef.scrollHeight > 42) {
        textareaRef.style.height = Math.min(textareaRef.scrollHeight, 120) + 'px';
      }
    }
  });
  
  // Audio recording state
  let isRecording = $state(false);
  let mediaStream = $state<MediaStream | null>(null);
  let mediaRecorder = $state<MediaRecorder | null>(null);
  let audioChunks: Blob[] = [];

  // System Status
  let apiConnected = $state(false);
  let statusBannerText = $state('Checking system connection...');
  let lastUpdatedTime = $state('Never');

  // Conversation logs
  interface ChatMessage {
    sender: 'user' | 'ai';
    name: string;
    time: string;
    text: string;
    bulletPoints?: Array<{ label: string; value: string; change: string; changeType: 'positive' | 'negative' | 'neutral' }>;
    showChart?: boolean;
    summary?: string;
  }

  let messages = $state<ChatMessage[]>([]);

  // General History / Saved Items
  interface HistoryItem {
    question: string;
    answer: string;
    time: string;
  }
  let queryHistory = $state<HistoryItem[]>([]);

  interface TranscriptItem {
    filename: string;
    size: string;
    text: string;
    time: string;
  }
  let audioTranscripts = $state<TranscriptItem[]>([]);

  // Clipboard Copied indicators
  let copiedIndex = $state<number | null>(null);

  // Chat Feed Scrolling
  let conversationFeedRef = $state<HTMLDivElement | null>(null);

  function scrollToBottom() {
    if (conversationFeedRef) {
      setTimeout(() => {
        conversationFeedRef!.scrollTo({
          top: conversationFeedRef!.scrollHeight,
          behavior: 'smooth'
        });
      }, 50);
    }
  }

  $effect(() => {
    if (messages.length > 0) {
      scrollToBottom();
    }
  });

  // --- COMPONENT MOUNT ---
  onMount(() => {
    // Sync theme with document class list (defaulting to dark mode)
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme === 'light') {
      isLightTheme = true;
      document.documentElement.classList.add('light-theme');
    } else {
      isLightTheme = false;
      document.documentElement.classList.remove('light-theme');
    }

    // ── Authentication Protection Guard ──
    (async () => {
      try {
        const clerk = await initClerk();
        if (!clerk.user) {
          // If unauthenticated, redirect to landing page where Sign In / Sign Up is available
          isAccessAllowed = false;
          authChecking = false;
          goto('/');
          return;
        }

        // Authenticated with Clerk — allow dashboard access immediately
        isAccessAllowed = true;
        authChecking = false;

        // Verify and sync with backend without blocking UI entry
        verifyWithBackend().then(() => {
          checkBackendHealth();
        }).catch((err) => {
          console.warn('Backend session verification note:', err);
          checkBackendHealth();
        });
      } catch (err) {
        console.error('Auth guard error:', err);
        isAccessAllowed = false;
        authChecking = false;
        goto('/');
      }
    })();

    const interval = setInterval(() => {
      if (isAccessAllowed) {
        checkBackendHealth();
      }
    }, 8000);
    return () => clearInterval(interval);
  });

  $effect(() => {
    // If user signs out while on the dashboard, redirect back to landing page
    if (!authChecking && !authState.isLoading && !authState.isAuthenticated) {
      goto('/');
    }
  });

  // --- ACTIONS ---

  // Theme Toggler
  function toggleTheme() {
    isLightTheme = !isLightTheme;
    if (isLightTheme) {
      document.documentElement.classList.add('light-theme');
      localStorage.setItem('theme', 'light');
    } else {
      document.documentElement.classList.remove('light-theme');
      localStorage.setItem('theme', 'dark');
    }
  }

  const RENDER_BACKEND_URL = 'https://real-estate-rag-backend.onrender.com';
  const LOCAL_BACKEND_URL = (import.meta.env.VITE_API_BASE_URL as string) || 'http://localhost:8000';

  let activeWorkingUrl: string | null = null;
  let API_BASE_URL = RENDER_BACKEND_URL;

  function isLocalEnvironment(): boolean {
    if (typeof window === 'undefined') return false;
    const hostname = window.location.hostname;
    return hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '0.0.0.0' || hostname === '';
  }

  // Environment-aware fetch helper: Production URL exclusively targets Render Backend
  async function fetchWithFallback(path: string, init?: RequestInit): Promise<Response> {
    const isLocal = isLocalEnvironment();

    // On Render/Production: NEVER query localhost:8000
    // On Localhost: query local backend first, with Render fallback
    const targets = isLocal
      ? [
          activeWorkingUrl,
          LOCAL_BACKEND_URL,
          'http://localhost:8000',
          'http://127.0.0.1:8000',
          RENDER_BACKEND_URL
        ]
      : [
          activeWorkingUrl,
          RENDER_BACKEND_URL,
          (import.meta.env.VITE_API_BASE_URL as string)
        ];

    const uniqueTargets = [...new Set(targets.filter(Boolean))] as string[];
    let lastError: any = null;

    for (const base of uniqueTargets) {
      const controller = new AbortController();
      // Allow 90s for Render free-tier cold starts, 75s for local AI processing & tool calling
      const timeoutMs = base.includes('onrender.com') ? 90000 : 75000;
      const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

      try {
        const cleanBase = base.replace(/\/+$/, '');
        const url = `${cleanBase}${path}`;
        const requestInit = {
          ...init,
          signal: controller.signal
        };

        const res = await fetch(url, requestInit);
        clearTimeout(timeoutId);
        if (res) {
          activeWorkingUrl = cleanBase;
          API_BASE_URL = cleanBase;
          return res;
        }
      } catch (err: any) {
        clearTimeout(timeoutId);
        if (err.name === 'AbortError') {
          console.warn(`Connection timeout for ${base}`);
        }
        lastError = err;
      }
    }
    activeWorkingUrl = null;
    throw lastError || new Error('Network error: Unable to connect to FastAPI backend server.');
  }


  const CHENNAI_COORDS: Record<string, [number, number]> = {
    'porur': [13.0382, 80.1565],
    'guindy': [13.0067, 80.2025],
    'velachery': [12.9815, 80.2180],
    'sholinganallur': [12.8996, 80.2279],
    'omr': [12.9416, 80.2362],
    'thoraipakkam': [12.9416, 80.2362],
    'chennai central': [13.0827, 80.2707],
    'central': [13.0827, 80.2707],
    'airport': [12.9941, 80.1709],
    'anna nagar': [13.0850, 80.2101],
    't nagar': [13.0418, 80.2341],
    'adyar': [13.0012, 80.2565],
    'tambaram': [12.9249, 80.1000],
    'medavakkam': [12.9185, 80.1902],
    'perumbakkam': [12.9038, 80.1983],
    'navalur': [12.8465, 80.2268],
    'siruseri': [12.8286, 80.2206],
    'kelambakkam': [12.7874, 80.2198],
    'egmore': [13.0822, 80.2607],
    'nungambakkam': [13.0604, 80.2396],
    'alandur': [12.9975, 80.2006],
    'mugalivakkam': [13.0238, 80.1652]
  };

  function getCoordinatesForPlace(name: string, defaultLat: number, defaultLon: number): [number, number] {
    const clean = name.toLowerCase().trim();
    for (const [key, coords] of Object.entries(CHENNAI_COORDS)) {
      if (clean.includes(key)) return coords;
    }
    return [defaultLat, defaultLon];
  }

  // Parse structured route details from assistant message for rendering real interactive Google Maps
  function getRouteMapData(text: string) {
    if (!text) return null;
    
    // 1. Match /api/v1/map/route parameters
    const mapUrlMatch = text.match(/\/api\/v1\/map\/route\?([^)\s"'>]+)/);
    // 2. Match Google Maps directions URL
    const gmapsMatch = text.match(/https:\/\/www\.google\.com\/maps\/dir\/\?[^)\s"'>]+/);
    // 3. Match Route markdown title: ![📍 Route Map: Porur to Velachery]
    const routeTitleMatch = text.match(/!\[(?:📍\s*)?(?:Route Map|Route):\s*([^to\n]+?)\s+to\s+([^\]\n]+)\]/i);
    // 4. Match general Route phrases in text
    const textRouteMatch = text.match(/(?:route|distance|travel|navigat\w*)\s+(?:from|between)\s+([A-Za-z0-9\s]+?)\s+(?:to|and)\s+([A-Za-z0-9\s,]+?)(?:\.|\n|,|$)/i);

    if (mapUrlMatch) {
      try {
        const params = new URLSearchParams(mapUrlMatch[1]);
        const origin = params.get('origin') || params.get('orig') || 'Porur';
        const destination = params.get('destination') || params.get('dest') || 'Velachery';
        const distKm = params.get('dist') || '14.4';
        const durationMins = params.get('time') || '30';
        const [cLat1, cLon1] = getCoordinatesForPlace(origin, 13.0382, 80.1565);
        const [cLat2, cLon2] = getCoordinatesForPlace(destination, 12.9815, 80.2180);
        const lat1 = parseFloat(params.get('lat1') || String(cLat1));
        const lon1 = parseFloat(params.get('lon1') || String(cLon1));
        const lat2 = parseFloat(params.get('lat2') || String(cLat2));
        const lon2 = parseFloat(params.get('lon2') || String(cLon2));
        const googleMapsUrl = gmapsMatch ? gmapsMatch[0] : `https://www.google.com/maps/dir/?api=1&origin=${encodeURIComponent(origin)}&destination=${encodeURIComponent(destination)}`;

        return { origin, destination, distKm, durationMins, lat1, lon1, lat2, lon2, googleMapsUrl };
      } catch (e) {
        console.error('Error parsing route map params:', e);
      }
    }

    if (gmapsMatch) {
      try {
        const urlObj = new URL(gmapsMatch[0]);
        const origin = decodeURIComponent(urlObj.searchParams.get('origin') || 'Porur');
        const destination = decodeURIComponent(urlObj.searchParams.get('destination') || 'Velachery');
        const distMatch = text.match(/(\d+(?:\.\d+)?)\s*(?:km|kilometers)/i);
        const timeMatch = text.match(/(\d+)\s*(?:mins?|minutes)/i);
        const [lat1, lon1] = getCoordinatesForPlace(origin, 13.0382, 80.1565);
        const [lat2, lon2] = getCoordinatesForPlace(destination, 12.9815, 80.2180);

        return {
          origin,
          destination,
          distKm: distMatch ? distMatch[1] : '14.4',
          durationMins: timeMatch ? timeMatch[1] : '30',
          lat1,
          lon1,
          lat2,
          lon2,
          googleMapsUrl: gmapsMatch[0]
        };
      } catch (e) {
        console.error('Error parsing gmaps match:', e);
      }
    }

    if (routeTitleMatch) {
      const origin = routeTitleMatch[1].trim();
      const destination = routeTitleMatch[2].trim();
      const distMatch = text.match(/(\d+(?:\.\d+)?)\s*(?:km|kilometers)/i);
      const timeMatch = text.match(/(\d+)\s*(?:mins?|minutes)/i);
      const [lat1, lon1] = getCoordinatesForPlace(origin, 13.0382, 80.1565);
      const [lat2, lon2] = getCoordinatesForPlace(destination, 12.9815, 80.2180);

      return {
        origin,
        destination,
        distKm: distMatch ? distMatch[1] : '14.4',
        durationMins: timeMatch ? timeMatch[1] : '30',
        lat1,
        lon1,
        lat2,
        lon2,
        googleMapsUrl: `https://www.google.com/maps/dir/?api=1&origin=${encodeURIComponent(origin)}&destination=${encodeURIComponent(destination)}`
      };
    }

    if (textRouteMatch && (text.includes('km') || text.includes('mins') || text.includes('Google Maps'))) {
      const origin = textRouteMatch[1].trim();
      const destination = textRouteMatch[2].trim();
      const distMatch = text.match(/(\d+(?:\.\d+)?)\s*(?:km|kilometers)/i);
      const timeMatch = text.match(/(\d+)\s*(?:mins?|minutes)/i);
      const [lat1, lon1] = getCoordinatesForPlace(origin, 13.0382, 80.1565);
      const [lat2, lon2] = getCoordinatesForPlace(destination, 12.9815, 80.2180);

      return {
        origin,
        destination,
        distKm: distMatch ? distMatch[1] : '14.4',
        durationMins: timeMatch ? timeMatch[1] : '30',
        lat1,
        lon1,
        lat2,
        lon2,
        googleMapsUrl: `https://www.google.com/maps/dir/?api=1&origin=${encodeURIComponent(origin)}&destination=${encodeURIComponent(destination)}`
      };
    }

    return null;
  }

  // Parse structured site visit booking details for rendering Google Calendar Event card
  function getCalendarBookingData(text: string) {
    if (!text) return null;
    const isVisitMatch = text.match(/(?:Site Visit|Site visit|site visit|Appointment|Booking Ref|Booking Reference|visit is scheduled|scheduled for|confirmed for)/i);
    const bookingIdMatch = text.match(/VISIT-[A-Z0-9]{4,8}/i);
    
    if (isVisitMatch && (bookingIdMatch || text.toLowerCase().includes('confirmed') || text.toLowerCase().includes('scheduled'))) {
      const propMatch = text.match(/(?:for|at)\s+([A-Z][A-Za-z0-9\s,–-]+?)(?:\s+on|\.|\n|$)/);
      const dateMatch = text.match(/(?:on|date:?)\s+([A-Za-z0-9\s,]+?)(?:\s+at|\.|\n|$)/i);
      const timeMatch = text.match(/(?:at|time:?)\s+(\d{1,2}:\d{2}\s*(?:AM|PM))/i);
      const nameMatch = text.match(/(?:customer|client|name:?)\s+([A-Za-z\s]+?)(?:\.|\n|$)/i);

      return {
        propertyName: propMatch ? propMatch[1].trim() : 'Prestige Courtyards, Sholinganallur',
        visitDate: dateMatch ? dateMatch[1].trim() : 'Upcoming Saturday',
        visitTime: timeMatch ? timeMatch[1].trim() : '11:00 AM',
        customerName: nameMatch ? nameMatch[1].trim() : 'Prospective Buyer',
        bookingId: bookingIdMatch ? bookingIdMatch[0] : 'VISIT-' + Math.random().toString(36).substring(2, 8).toUpperCase(),
        notes: 'Site Visit & Property Tour'
      };
    }
    return null;
  }

  function formatMessageText(text: string): string {
    if (!text) return '';
    let formatted = text
      .replace(/\[METADATA\][^\n]*\n?/gi, '')
      .replace(/(?:We found|There are)\s+\d+\s+matching properties[^\n]*\n?/gi, '')
      .replace(/Here are the top \d+ matching properties:?\n?/gi, '')
      .replace(/(?:Total matching properties|Matching properties count)(?: found)?:?\s*\d*\.?\n?/gi, '')
      .replace(/(?:Matching_Count|matching_count):\s*\d+\.?\n?/gi, '')
      .replace(/(?:Average_Property_Price|average_price):\s*(?:Rs\s*)?([\d\.]+)\s*(?:Lakhs)?/gi, 'The average property price is ₹$1 Lakhs.')
      .replace(/Exact_Match_Found:\s*(true|false)/gi, '')
      .replace(/Total_Database_Listings:\s*(\d+)/gi, '')
      .replace(/Average_Property_Price:/gi, 'Average Property Price:')
      .replace(/Matching_Count:/gi, '')
      .replace(/Exact_Match_Found:/gi, '')
      .trim();

    // Remove any raw markdown image tags to prevent broken img placeholders
    formatted = formatted.replace(/!\[(.*?)\]\((.+?)\)/g, '');

    // Convert Google Maps & external markdown links [text](url) to styled interactive buttons
    formatted = formatted.replace(
      /\[(.*?)\]\((https?:\/\/[^\s\)]+)\)/g,
      '<a href="$2" target="_blank" rel="noopener noreferrer" class="map-link-btn">$1 <svg style="display:inline;vertical-align:middle;margin-left:4px;" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg></a>'
    );

    // 3. Convert markdown bold **text** to <strong>text</strong>
    formatted = formatted.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

    // 4. Convert newlines to breaks
    formatted = formatted.replace(/\n/g, '<br />');
    
    return formatted;
  }


  // Health check polling
  async function checkBackendHealth() {
    try {
      const res = await fetchWithFallback('/');
      if (res.ok) {
        apiConnected = true;
        statusBannerText = 'All systems operational';
      } else {
        apiConnected = false;
        statusBannerText = 'Backend server returned error status';
      }
    } catch (e) {
      apiConnected = false;
      statusBannerText = 'Connection failed: Connecting to backend server...';
    }
    const d = new Date();
    lastUpdatedTime = d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  }

  // Send RAG Search Query
  async function sendQuestion(questionText: string) {
    if (!questionText || !questionText.trim() || isAsking) return;
    
    const currentQuestion = questionText.trim();
    quickAskQuestion = '';
    isAsking = true;
    
    // Add user message immediately
    const userTime = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    messages.push({
      sender: 'user',
      name: 'You',
      time: 'Today, ' + userTime,
      text: currentQuestion
    });

    // Create a temporary loading message from AI
    messages.push({
      sender: 'ai',
      name: 'AI Assistant',
      time: 'Today, ' + userTime,
      text: 'Retrieving vector listings and generating answers...'
    });

    try {
      const historyPayload = messages
        .filter(m => m.text && !m.text.includes('Retrieving vector listings'))
        .map(m => ({ sender: m.sender, text: m.text }));

      const response = await fetchWithFallback('/ask', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ 
          question: currentQuestion,
          history: historyPayload
        })
      });

      if (!response.ok) {
        throw new Error('API server returned error status ' + response.status);
      }

      const data = await response.json();
      
      // Remove loading message
      messages.pop();

      // Parse answer text for lines or bullet points
      const rawAnswer = data.answer || "I couldn't find a suitable property based on the available data.";
      
      // Separate basic response
      messages.push({
        sender: 'ai',
        name: 'AI Assistant',
        time: 'Today, ' + new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        text: rawAnswer
      });

      // Save to general history
      queryHistory.push({
        question: currentQuestion,
        answer: rawAnswer,
        time: new Date().toLocaleString()
      });

    } catch (err: any) {
      messages.pop(); // Remove loading
      messages.push({
        sender: 'ai',
        name: 'AI Assistant',
        time: 'Today, ' + new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        text: `Error: Unable to complete request. Details: ${err.message}. Please verify the FastAPI backend is running.`
      });
    } finally {
      isAsking = false;
      checkBackendHealth();
    }
  }

  // Voice Recording & Real-time Speech Recognition
  let speechRecognition: any = null;

  async function toggleRecording() {
    if (isRecording) {
      if (speechRecognition) {
        try { speechRecognition.stop(); } catch (_) {}
        speechRecognition = null;
      }
      if (mediaRecorder && mediaRecorder.state !== 'inactive') {
        try { mediaRecorder.stop(); } catch (_) {}
      }
      isRecording = false;
      return;
    }

    // 1. Try Browser Native Web Speech API first (Real-time live typing)
    const SpeechRecognitionClass = typeof window !== 'undefined' && ((window as any).SpeechRecognition || (window as any).webkitSpeechRecognition);
    if (SpeechRecognitionClass) {
      try {
        speechRecognition = new SpeechRecognitionClass();
        speechRecognition.continuous = false;
        speechRecognition.interimResults = true;
        speechRecognition.lang = 'en-US';

        let initialPromptText = quickAskQuestion;
        let speechCapturedText = '';

        speechRecognition.onstart = () => {
          isRecording = true;
        };

        speechRecognition.onresult = (event: any) => {
          let interim = '';
          let final = '';
          for (let i = event.resultIndex; i < event.results.length; ++i) {
            if (event.results[i].isFinal) {
              final += event.results[i][0].transcript;
            } else {
              interim += event.results[i][0].transcript;
            }
          }
          speechCapturedText = (final + ' ' + interim).trim();
          if (speechCapturedText) {
            quickAskQuestion = initialPromptText ? (initialPromptText + ' ' + speechCapturedText) : speechCapturedText;
          }
        };

        speechRecognition.onerror = (event: any) => {
          console.warn('SpeechRecognition error event:', event.error);
          isRecording = false;
          speechRecognition = null;
          if (event.error === 'network' || event.error === 'service-not-allowed' || event.error === 'no-speech') {
            startMediaRecorderFallback();
          }
        };

        speechRecognition.onend = () => {
          isRecording = false;
          speechRecognition = null;
          if (speechCapturedText) {
            audioTranscripts.push({
              filename: 'Live Voice Search',
              size: '0.01MB',
              text: speechCapturedText,
              time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
            });
          }
        };

        speechRecognition.start();
        return;
      } catch (err) {
        console.warn('SpeechRecognition initialization error, falling back to MediaRecorder:', err);
      }
    }

    // 2. Fallback to MediaRecorder + Backend API
    await startMediaRecorderFallback();
  }

  async function startMediaRecorderFallback() {
    try {
      mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorder = new MediaRecorder(mediaStream);
      audioChunks = [];

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunks.push(event.data);
        }
      };

      mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
        const file = new File([audioBlob], 'voice-input.webm', { type: 'audio/webm' });
        
        if (mediaStream) {
          mediaStream.getTracks().forEach(track => track.stop());
        }

        await transcribeAudioBlob(file);
      };

      mediaRecorder.start();
      isRecording = true;
    } catch (err) {
      alert('Microphone access denied or unavailable. Please check your mic permissions in browser settings.');
      console.error(err);
    }
  }

  async function transcribeAudioBlob(file: File) {
    isTranscribing = true;
    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetchWithFallback('/transcribe', {
        method: 'POST',
        body: formData
      });

      if (!res.ok) {
        throw new Error(`Server returned status ${res.status}`);
      }

      const data = await res.json();
      const transcribedText = (data.text || '').trim();

      if (transcribedText) {
        quickAskQuestion = (quickAskQuestion ? quickAskQuestion + ' ' : '') + transcribedText;
        
        audioTranscripts.push({
          filename: 'Voice Search Record',
          size: (file.size / (1024 * 1024)).toFixed(2) + 'MB',
          text: transcribedText,
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        });
      } else {
        console.log('No clear speech detected in recording.');
      }
    } catch (err: any) {
      console.error('Voice search transcription error:', err);
    } finally {
      isTranscribing = false;
      checkBackendHealth();
    }
  }

  function copyToClipboard(text: string, index: number) {
    navigator.clipboard.writeText(text);
    copiedIndex = index;
    setTimeout(() => {
      if (copiedIndex === index) copiedIndex = null;
    }, 2000);
  }

  // Re-ask from query history
  function reloadQuery(question: string) {
    quickAskQuestion = question;
    activeSidebarTab = 'Dashboard';
  }
</script>

{#if authChecking}
  <div class="auth-loading-screen animate-fade-in">
    <div class="auth-loading-card glass-panel">
      <div class="auth-spinner-ring"></div>
      <div class="auth-status-text">
        <h3>Securing Session</h3>
        <p>Verifying authentication credentials...</p>
      </div>
    </div>
  </div>
{:else if isAccessAllowed}
<div class="dashboard-container">
  
  {#if mobileMenuOpen}
    <!-- Mobile Navigation Backdrop -->
    <button type="button" aria-label="Close mobile navigation backdrop" class="mobile-backdrop" onclick={() => mobileMenuOpen = false}></button>
  {/if}

  <!-- SIDEBAR NAVIGATION -->
  <aside class="sidebar" class:collapsed={sidebarCollapsed} class:mobile-open={mobileMenuOpen}>
    <div class="sidebar-top">
      <div class="logo-box">
        <a href="/" class="home-logo-btn" title="Back to Landing Page">
          <Building2 size={22} class="home-svg-icon" />
        </a>
        {#if !sidebarCollapsed || mobileMenuOpen}
          <div class="logo-text">
            <h2>Real Estate AI Assistant</h2>
            <span class="logo-ver">v0.1.0</span>
          </div>
        {/if}
        <button class="mobile-close-btn icon-btn" onclick={() => mobileMenuOpen = false} title="Close menu">
          <X size={20} />
        </button>
      </div>

      <nav class="sidebar-menu">
        <button 
          class="menu-item" 
          class:active={activeSidebarTab === 'Dashboard'} 
          onclick={() => { activeSidebarTab = 'Dashboard'; mobileMenuOpen = false; }}
          title="Dashboard"
        >
          <LayoutDashboard size={20} />
          {#if !sidebarCollapsed || mobileMenuOpen}
            <span>Dashboard</span>
          {/if}
        </button>

        <button 
          class="menu-item" 
          class:active={activeSidebarTab === 'Query History'} 
          onclick={() => { activeSidebarTab = 'Query History'; mobileMenuOpen = false; }}
          title="Query History"
        >
          <History size={20} />
          {#if !sidebarCollapsed || mobileMenuOpen}
            <span>Query History</span>
            <span class="count-badge">{queryHistory.length}</span>
          {/if}
        </button>

        <button 
          class="menu-item" 
          class:active={activeSidebarTab === 'Connectors'} 
          onclick={() => { activeSidebarTab = 'Connectors'; mobileMenuOpen = false; }}
          title="MCP Connectors & OAuth"
        >
          <Plug size={20} />
          {#if !sidebarCollapsed || mobileMenuOpen}
            <span>Connectors</span>
          {/if}
        </button>
      </nav>
    </div>

    <!-- Collapse Toggle button at bottom -->
    <button class="collapse-btn" onclick={() => sidebarCollapsed = !sidebarCollapsed}>
      {#if sidebarCollapsed}
        <ChevronRight size={18} />
      {:else}
        <ChevronLeft size={18} />
        <span>Collapse</span>
      {/if}
    </button>
  </aside>

  <!-- MAIN WORKSPACE -->
  <div class="workspace">
    
    <!-- TOP HEADER -->
    <header class="workspace-header">
      <div class="header-left">
        <button class="mobile-menu-btn icon-btn" onclick={() => mobileMenuOpen = !mobileMenuOpen} title="Toggle Navigation Menu">
          <Menu size={22} />
        </button>
        <h1>{activeSidebarTab}</h1>
      </div>
      
      <div class="header-right">
        <!-- Theme Toggle -->
        <button class="icon-btn" onclick={toggleTheme} title="Toggle Theme">
          {#if isLightTheme}
            <Moon size={20} />
          {:else}
            <Sun size={20} />
          {/if}
        </button>
        
        <!-- Settings -->
        <button class="icon-btn" title="Settings" onclick={() => alert(`System Settings:\nConnected Backend: ${API_BASE_URL}\nStatus: ${apiConnected ? 'Connected' : 'Disconnected'}`)}>
          <Settings size={20} />
        </button>

        <div class="divider"></div>

        <!-- User Auth (Clerk) -->
        <AuthHeader />
      </div>
    </header>

    <!-- VIEWS CONTROLLER BASED ON TAB -->
    <main class="workspace-content">
      
      {#if activeSidebarTab === 'Dashboard'}
        <div class="dashboard-grid">
            <!-- CONVERSATION HISTORY LOGS -->
            <section class="glass-panel card-box conversation-card">
              <div class="card-header">
                <div class="title-with-icon">
                  <svg class="header-blue-icon" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.5">
                    <circle cx="12" cy="12" r="10"/>
                    <path d="M8 12h8"/>
                    <path d="M12 8v8"/>
                  </svg>
                  <h3>Conversation</h3>
                </div>
              </div>

              <div class="conversation-feed" bind:this={conversationFeedRef}>
                {#if messages.length === 0}
                  <div class="empty-conversation animate-fade-in">
                    <div class="empty-convo-icon">
                      <Building2 size={32} color="#060913" />
                    </div>
                    <h4>Your Conversation Starts Here</h4>
                    <p>Ask a question about property values, market trends, or listings to begin RAG retrieval analysis.</p>
                    <div class="empty-convo-suggestions">
                      <button onclick={() => quickAskQuestion = "What are the nearby metro stations and hospitals around Sholinganallur OMR?"}>
                        📍 "Nearby metro & hospitals for Sholinganallur"
                      </button>
                      <button onclick={() => quickAskQuestion = "Calculate EMI for 75 Lakhs home loan at 8.5% for 20 years with interest breakdown"}>
                        🧮 "Calculate EMI for 75L loan (20 yrs)"
                      </button>
                      <button onclick={() => quickAskQuestion = "Show on-road cost & stamp duty breakdown for an 80 Lakhs property (1250 sqft)"}>
                        💰 "Stamp duty & price/sqft for 80L"
                      </button>
                      <button onclick={() => quickAskQuestion = "Book a property site visit for Prestige Courtyards this Saturday at 11:00 AM for Anbarasu (9876543210)"}>
                        📅 "Book site visit for Prestige Courtyards"
                      </button>
                    </div>
                  </div>
                {:else}
                  {#each messages as msg, i}
                    <div class="chat-bubble-container" class:user-bubble={msg.sender === 'user'}>
                      <div class="bubble-header">
                        <div class="bubble-avatar" style="background-color: {msg.sender === 'user' ? '#59FF00' : '#4cd600'};">
                          {#if msg.sender === 'user'}
                            <User size={14} color="#060913" />
                          {:else}
                            <Building2 size={14} color="#060913" />
                          {/if}
                        </div>
                        <span class="bubble-sender">{msg.name}</span>
                        <span class="bubble-time">{msg.time}</span>
                      </div>

                      <div class="bubble-text">
                        {#if formatMessageText(msg.text)}
                          <p>{@html formatMessageText(msg.text)}</p>
                        {/if}

                        <!-- Render Real Interactive Google-Maps-Style Route Map in Chat -->
                        {#if msg.sender !== 'user' && getRouteMapData(msg.text)}
                          {@const routeInfo = getRouteMapData(msg.text)}
                          {#if routeInfo}
                            <ChatRouteMap
                              origin={routeInfo.origin}
                              destination={routeInfo.destination}
                              distKm={routeInfo.distKm}
                              durationMins={routeInfo.durationMins}
                              lat1={routeInfo.lat1}
                              lon1={routeInfo.lon1}
                              lat2={routeInfo.lat2}
                              lon2={routeInfo.lon2}
                              googleMapsUrl={routeInfo.googleMapsUrl}
                            />
                          {/if}
                        {/if}

                        <!-- Render Google Calendar Event Card in Chat -->
                        {#if msg.sender !== 'user' && getCalendarBookingData(msg.text)}
                          {@const calInfo = getCalendarBookingData(msg.text)}
                          {#if calInfo}
                            <ChatCalendarCard
                              propertyName={calInfo.propertyName}
                              visitDate={calInfo.visitDate}
                              visitTime={calInfo.visitTime}
                              customerName={calInfo.customerName}
                              bookingId={calInfo.bookingId}
                              notes={calInfo.notes}
                            />
                          {/if}
                        {/if}
                        
                        <!-- Render Bullet Stats for initial Austin Trend response -->
                        {#if msg.bulletPoints}
                          <ul class="bullet-list">
                            {#each msg.bulletPoints as bp}
                              <li>
                                <span class="bullet-label">{bp.label}:</span>
                                <strong class="bullet-val">{bp.value}</strong>
                                {#if bp.change}
                                  <span class="bullet-change" class:positive={bp.changeType === 'positive'} class:neutral={bp.changeType === 'neutral'}>
                                    ({bp.change})
                                  </span>
                                {/if}
                              </li>
                            {/each}
                          </ul>
                        {/if}

                        {#if msg.summary}
                          <p class="summary-text">{msg.summary}</p>
                        {/if}
                      </div>
                    </div>
                  {/each}
                {/if}
              </div>
            </section>

            <!-- QUICK ASK CARD -->
            <section class="glass-panel card-box quick-ask-card">
              <div class="card-header quick-ask-header">
                <div class="title-with-icon">
                  <svg class="header-blue-icon" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.5">
                    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
                  </svg>
                  <h3>Quick Ask</h3>
                </div>
              </div>

              <div class="quick-ask-body">
                <textarea 
                  bind:this={textareaRef}
                  placeholder="Ask in English or Tanglish (e.g., '3 BHK in Egmore')..."
                  bind:value={quickAskQuestion}
                  disabled={isAsking}
                  onkeydown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      sendQuestion(quickAskQuestion);
                    }
                  }}
                ></textarea>
                
                <div class="quick-ask-footer">
                   <div class="action-buttons-group">
                      <button 
                        class="btn-primary voice-btn" 
                        class:recording={isRecording}
                        class:transcribing={isTranscribing}
                        title={isRecording ? "Stop Recording" : isTranscribing ? "Transcribing..." : "Voice Search"} 
                        onclick={toggleRecording}
                        disabled={isAsking}
                        type="button"
                      >
                        {#if isTranscribing}
                          <span class="mini-spinner"></span>
                        {:else}
                          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke={isRecording ? "#ef4444" : "#060913"} stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" class="mic-svg">
                            <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/>
                            <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
                            <line x1="12" y1="19" x2="12" y2="22"/>
                          </svg>
                        {/if}
                      </button>
                     
                      <button 
                        class="btn-primary send-btn" 
                        onclick={() => sendQuestion(quickAskQuestion)}
                        disabled={isAsking || !quickAskQuestion.trim()}
                      >
                        {#if isAsking}
                          <span class="spinner"></span>
                          <span>Processing...</span>
                        {:else}
                          <Send size={14} />
                          <span>Send Question</span>
                        {/if}
                      </button>
                   </div>
                 </div>
              </div>
            </section>
        </div>
      
      {:else}
        
        <!-- OTHER NAVIGATION VIEWS -->
        <div class="other-view-container glass-panel animate-fade-in">
          
          {#if activeSidebarTab === 'Query History'}
            <div class="history-view">
              <h3>Saved Ask Sessions</h3>
              <p class="section-subtitle">A collection of questions posed to the vector retrieval engine.</p>
              
              {#if queryHistory.length === 0}
                <div class="empty-state">
                  <History size={48} class="text-muted" />
                  <p>No queries recorded in this session yet.</p>
                </div>
              {:else}
                <div class="history-list">
                  {#each queryHistory as item, index}
                    <div class="history-item-row">
                      <div class="history-meta">
                        <span class="history-time">{item.time}</span>
                        <button class="reload-btn" onclick={() => reloadQuery(item.question)}>
                          Run Again <ArrowUpRight size={14} />
                        </button>
                      </div>
                      <div class="history-content">
                        <strong>Q: {item.question}</strong>
                        <p>A: {item.answer.substring(0, 150)}...</p>
                      </div>
                    </div>
                  {/each}
                </div>
              {/if}
            </div>
          {:else if activeSidebarTab === 'Connectors'}
            <ConnectorsView onBack={() => activeSidebarTab = 'Dashboard'} />
          {/if}
          
        </div>
      {/if}

    </main>
  </div>

</div>
{/if}

<style>
  /* --- AUTH LOADING SCREEN --- */
  .auth-loading-screen {
    width: 100vw;
    height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    background-color: var(--bg-primary);
    padding: 1.5rem;
  }

  .auth-loading-card {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 1.25rem;
    padding: 2.5rem 3rem;
    text-align: center;
    max-width: 400px;
    border-radius: 16px;
    border: 1px solid rgba(89, 255, 0, 0.25);
    box-shadow: 0 16px 40px rgba(0, 0, 0, 0.5), 0 0 25px rgba(89, 255, 0, 0.1);
  }

  .auth-spinner-ring {
    width: 42px;
    height: 42px;
    border: 3px solid rgba(89, 255, 0, 0.2);
    border-top-color: #59FF00;
    border-radius: 50%;
    animation: authSpin 0.9s cubic-bezier(0.5, 0.1, 0.5, 0.9) infinite;
  }

  @keyframes authSpin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
  }

  .auth-status-text h3 {
    font-size: 1.15rem;
    color: #ffffff;
    font-weight: 700;
    margin-bottom: 0.35rem;
  }

  .auth-status-text p {
    font-size: 0.85rem;
    color: var(--text-secondary);
    margin: 0;
  }
  /* --- LAYOUT GRID --- */
  .dashboard-container {
    display: flex;
    width: 100vw;
    height: 100vh;
    overflow: hidden;
    background-color: var(--bg-primary);
  }

  /* --- SIDEBAR --- */
  .sidebar {
    width: 250px;
    height: 100%;
    background-color: var(--bg-secondary);
    border-right: 1px solid var(--border-light);
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    padding: 1.5rem 1rem;
    transition: width var(--transition-normal);
    z-index: 10;
    flex-shrink: 0;
    overflow: hidden;
  }

  .sidebar.collapsed {
    width: 72px;
    padding: 1.5rem 0.6rem;
  }

  .sidebar.collapsed:not(.mobile-open) .menu-item {
    justify-content: center;
    padding: 10px 0;
    gap: 0;
  }

  .sidebar.collapsed:not(.mobile-open) .menu-item span,
  .sidebar.collapsed:not(.mobile-open) .count-badge {
    display: none;
  }

  .sidebar.collapsed:not(.mobile-open) .logo-box {
    justify-content: center;
    padding-left: 0;
  }

  .sidebar.collapsed:not(.mobile-open) .collapse-btn {
    justify-content: center;
    padding: 10px 0;
    gap: 0;
  }

  .sidebar-top {
    display: flex;
    flex-direction: column;
    gap: 2.2rem;
  }

  .logo-box {
    display: flex;
    align-items: center;
    gap: 12px;
    padding-left: 0.5rem;
  }

  .home-logo-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    background-color: var(--color-primary);
    color: #ffffff;
    width: 36px;
    height: 36px;
    border-radius: 8px;
    transition: background-color var(--transition-fast);
    flex-shrink: 0;
  }

  .home-logo-btn:hover {
    background-color: var(--color-primary-hover);
  }

  .home-svg-icon {
    width: 18px;
    height: 18px;
  }

  .logo-text h2 {
    font-size: 1rem;
    font-weight: 700;
    color: var(--text-primary);
    line-height: 1.1;
  }

  .logo-ver {
    font-size: 0.7rem;
    color: var(--text-muted);
    font-family: var(--font-body);
  }

  .sidebar-menu {
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
  }

  .menu-item {
    display: flex;
    align-items: center;
    gap: 12px;
    background: none;
    border: none;
    padding: 10px 14px;
    border-radius: 8px;
    color: var(--text-secondary);
    font-family: var(--font-display);
    font-weight: 500;
    font-size: 0.9rem;
    cursor: pointer;
    text-align: left;
    width: 100%;
    transition: background-color var(--transition-fast), color var(--transition-fast);
    white-space: nowrap;
    overflow: hidden;
  }

  .menu-item span {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .menu-item:hover {
    background-color: rgba(255, 255, 255, 0.04);
    color: var(--text-primary);
  }

  .light-theme .menu-item:hover {
    background-color: rgba(0, 0, 0, 0.04);
  }

  .menu-item.active {
    background-color: var(--color-primary);
    color: #ffffff;
  }

  .count-badge {
    margin-left: auto;
    font-size: 0.75rem;
    background: rgba(255, 255, 255, 0.15);
    color: var(--text-primary);
    padding: 1px 6px;
    border-radius: 10px;
    font-weight: 600;
  }

  .green-badge {
    background-color: var(--color-success-bg);
    color: var(--color-success);
  }



  .collapse-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    background: none;
    border: none;
    color: var(--text-muted);
    font-size: 0.85rem;
    font-family: var(--font-display);
    font-weight: 500;
    padding: 10px;
    cursor: pointer;
    border-radius: 8px;
    transition: color var(--transition-fast), background-color var(--transition-fast);
  }

  .collapse-btn:hover {
    color: var(--text-primary);
    background-color: rgba(255, 255, 255, 0.04);
  }

  /* --- WORKSPACE --- */
  .workspace {
    flex-grow: 1;
    height: 100%;
    display: flex;
    flex-direction: column;
    background-color: var(--bg-primary);
    overflow: hidden;
  }

  /* --- HEADER --- */
  .workspace-header {
    height: 64px;
    border-bottom: 1px solid var(--border-light);
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0 2rem;
    background-color: var(--bg-secondary);
    flex-shrink: 0;
  }

  .workspace-header h1 {
    font-size: 1.25rem;
    color: var(--text-primary);
  }

  .header-right {
    display: flex;
    align-items: center;
    gap: 0.75rem;
  }

  .icon-btn {
    background: none;
    border: none;
    color: var(--text-secondary);
    cursor: pointer;
    width: 36px;
    height: 36px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: background-color var(--transition-fast), color var(--transition-fast);
  }

  .icon-btn:hover {
    background-color: rgba(255, 255, 255, 0.04);
    color: var(--text-primary);
  }

  .light-theme .icon-btn:hover {
    background-color: rgba(0, 0, 0, 0.04);
  }

  .divider {
    width: 1px;
    height: 24px;
    background-color: var(--border-light);
    margin: 0 0.5rem;
  }

  .user-profile {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .avatar {
    width: 32px;
    height: 32px;
    border-radius: 50%;
    background-color: var(--color-primary);
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .username {
    font-size: 0.9rem;
    font-weight: 600;
    color: var(--text-primary);
  }

  /* --- WORKSPACE CONTENT --- */
  .workspace-content {
    flex-grow: 1;
    padding: 1.5rem;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  /* --- DASHBOARD GRID --- */
  .dashboard-grid {
    display: flex;
    flex-direction: column;
    gap: 1rem;
    flex-grow: 1;
    overflow: hidden;
  }

  .conversation-card {
    flex-grow: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .quick-ask-card {
    flex-shrink: 0;
  }

  /* --- CARDS --- */
  .card-box {
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .card-header {
    padding: 1.25rem 1.5rem;
    border-bottom: 1px solid var(--border-light);
  }

  .title-with-icon {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .header-blue-icon {
    color: var(--color-accent);
  }

  .card-header h3 {
    font-size: 1.05rem;
    color: var(--text-primary);
  }

  .api-tag {
    font-family: monospace;
    font-size: 0.75rem;
    background: rgba(255, 255, 255, 0.05);
    color: var(--text-muted);
    padding: 2px 6px;
    border-radius: 4px;
    border: 1px solid var(--border-light);
    margin-left: 6px;
  }

  .light-theme .api-tag {
    background: rgba(0, 0, 0, 0.03);
  }

  /* --- QUICK ASK BOX --- */
  .quick-ask-header {
    padding: 0.6rem 1rem;
  }

  .quick-ask-header h3 {
    font-size: 0.95rem;
  }

  .quick-ask-body {
    padding: 0.65rem 1rem;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .quick-ask-body textarea {
    width: 100%;
    height: 38px;
    min-height: 38px;
    max-height: 120px;
    background-color: rgba(0, 0, 0, 0.08);
    border: 1px solid var(--border-light);
    border-radius: 6px;
    padding: 8px 12px;
    color: var(--text-primary);
    font-family: var(--font-body);
    font-size: 0.86rem;
    line-height: 1.4;
    resize: none;
    outline: none;
    transition: border-color var(--transition-fast), background-color var(--transition-fast);
    overflow-y: auto;
  }

  .light-theme .quick-ask-body textarea {
    background-color: #f8fafc;
  }

  .quick-ask-body textarea:focus {
    border-color: var(--color-accent);
  }

  .quick-ask-footer {
    display: flex;
    justify-content: flex-end;
    align-items: center;
  }

  .editor-tools {
    display: flex;
    gap: 0.5rem;
  }

  .action-buttons-group {
    display: flex;
    gap: 0.5rem;
    align-items: center;
  }

  .tool-btn {
    background: none;
    border: 1px solid var(--border-light);
    color: var(--text-secondary);
    width: 32px;
    height: 32px;
    border-radius: 6px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: background-color var(--transition-fast), color var(--transition-fast);
  }

  .voice-btn {
    width: 34px !important;
    height: 34px !important;
    min-height: 34px !important;
    min-width: 34px !important;
    padding: 0 !important;
    border-radius: 6px !important;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    background-color: var(--color-primary, #59FF00) !important;
    border: none !important;
    color: #060913 !important;
    cursor: pointer;
    box-shadow: 0 2px 8px rgba(89, 255, 0, 0.2);
    flex-shrink: 0;
  }

  .send-btn {
    height: 34px !important;
    min-height: 34px !important;
    padding: 4px 14px !important;
    font-size: 0.82rem !important;
    border-radius: 6px !important;
  }

  .voice-btn:hover {
    background-color: var(--color-primary-hover, #4cd600) !important;
    transform: translateY(-1px);
    box-shadow: 0 6px 16px rgba(89, 255, 0, 0.35);
  }

  .voice-btn .mic-svg {
    stroke: #060913 !important;
    display: block;
  }

  .voice-btn.recording .mic-svg {
    stroke: #ef4444 !important;
  }

  .tool-btn:hover {
    background-color: rgba(255, 255, 255, 0.04);
    color: var(--text-primary);
  }

  .light-theme .tool-btn:hover {
    background-color: rgba(0, 0, 0, 0.04);
  }

  .send-btn {
    min-width: 150px;
  }

  /* --- CONVERSATION FEED --- */
  .conversation-feed {
    padding: 1.5rem;
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
    flex-grow: 1;
    overflow-y: auto;
  }

  .chat-bubble-container {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    max-width: 82%;
    align-self: flex-start;
    align-items: flex-start;
  }

  .chat-bubble-container.user-bubble {
    align-self: flex-end;
    align-items: flex-end;
  }

  .chat-bubble-container.user-bubble .bubble-header {
    flex-direction: row-reverse;
  }

  .chat-bubble-container.user-bubble .bubble-text {
    background-color: rgba(89, 255, 0, 0.1);
    border-color: rgba(89, 255, 0, 0.25);
    border-top-right-radius: 2px;
  }

  .light-theme .chat-bubble-container.user-bubble .bubble-text {
    background-color: rgba(16, 185, 129, 0.1);
    border-color: rgba(16, 185, 129, 0.25);
  }

  .chat-bubble-container:not(.user-bubble) .bubble-text {
    border-top-left-radius: 2px;
  }

  .bubble-header {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .bubble-avatar {
    width: 24px;
    height: 24px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }

  .bubble-sender {
    font-size: 0.85rem;
    font-weight: 600;
    color: var(--text-primary);
  }

  .bubble-time {
    font-size: 0.75rem;
    color: var(--text-muted);
  }

  .bubble-text {
    width: fit-content;
    max-width: 100%;
    height: auto;
    min-height: auto;
    background-color: rgba(255, 255, 255, 0.03);
    border: 1px solid var(--border-light);
    border-radius: 12px;
    padding: 0.4rem 0.75rem;
    font-size: 0.9rem;
    line-height: 1.35;
    color: var(--text-primary);
    white-space: pre-wrap;
    word-break: break-word;
    overflow-wrap: anywhere;
    box-sizing: border-box;
  }

  .bubble-text p {
    margin: 0 !important;
    padding: 0 !important;
    line-height: 1.35;
    display: inline-block;
  }

  .light-theme .bubble-text {
    background-color: #f8fafc;
  }

  .bullet-list {
    margin: 1rem 0 1rem 1.25rem;
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
  }

  .bullet-label {
    color: var(--text-secondary);
  }

  .bullet-val {
    color: var(--text-primary);
    margin-left: 4px;
  }

  .bullet-change {
    font-size: 0.8rem;
    margin-left: 6px;
  }

  .bullet-change.positive {
    color: var(--color-success);
  }

  .bullet-change.neutral {
    color: var(--text-muted);
  }

  .summary-text {
    margin-top: 1rem;
    border-top: 1px solid var(--border-light);
    padding-top: 0.8rem;
    color: var(--text-secondary);
  }

  /* --- SVG CHART --- */
  .chart-container {
    margin-top: 1rem;
    padding: 1rem;
    border-radius: 12px;
  }

  .chart-header-row h5 {
    font-size: 0.85rem;
    color: var(--text-primary);
    margin-bottom: 0.5rem;
  }

  .svg-wrapper {
    width: 100%;
    margin-top: 0.5rem;
  }

  /* --- VOICE INTERFACE --- */
  .voice-body {
    padding: 1.5rem;
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .dropzone {
    border: 2px dashed rgba(59, 130, 246, 0.35);
    background: rgba(59, 130, 246, 0.02);
    border-radius: 12px;
    padding: 2rem 1.5rem;
    text-align: center;
    cursor: pointer;
    transition: background-color var(--transition-fast), border-color var(--transition-fast);
    outline: none;
  }

  .dropzone:hover, .dropzone.dragover {
    background-color: rgba(59, 130, 246, 0.06);
    border-color: var(--color-accent);
  }

  .upload-icon {
    color: var(--color-accent);
    margin-bottom: 0.75rem;
  }

  .drop-text {
    font-size: 0.85rem;
    color: var(--text-primary);
    font-weight: 500;
  }

  .sub-text {
    font-size: 0.78rem;
    color: var(--text-muted);
  }

  .hidden-file-input {
    display: none;
  }

  .selected-file-card {
    background-color: rgba(255, 255, 255, 0.02);
    border: 1px solid var(--border-light);
    border-radius: 8px;
    padding: 10px 14px;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .light-theme .selected-file-card {
    background-color: #ffffff;
  }

  .file-details {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 0.82rem;
    overflow: hidden;
  }

  .file-name {
    color: var(--text-primary);
    font-weight: 600;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 140px;
  }

  .file-size {
    color: var(--text-muted);
  }

  .clear-file-btn {
    background: none;
    border: none;
    color: var(--text-muted);
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .clear-file-btn:hover {
    color: #ef4444;
  }

  .transcribe-btn {
    width: 100%;
  }

  /* Audio Waves Loader Animation */
  .audio-waves-loader {
    display: flex;
    align-items: center;
    gap: 3px;
    height: 18px;
  }

  .audio-waves-loader span {
    width: 3px;
    height: 100%;
    background-color: #ffffff;
    border-radius: 3px;
    animation: bounce 0.8s infinite ease-in-out;
  }

  .audio-waves-loader span:nth-child(2) { animation-delay: 0.15s; }
  .audio-waves-loader span:nth-child(3) { animation-delay: 0.3s; }
  .audio-waves-loader span:nth-child(4) { animation-delay: 0.45s; }

  @keyframes bounce {
    0%, 100% { transform: scaleY(0.3); }
    50% { transform: scaleY(1); }
  }

  /* --- SYSTEM STATUS --- */
  .status-body {
    padding: 1.5rem;
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .status-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid var(--border-light);
    padding-bottom: 0.75rem;
    font-size: 0.88rem;
  }

  .status-row:last-of-type {
    border-bottom: none;
    padding-bottom: 0;
  }

  .status-label {
    color: var(--text-secondary);
  }

  .status-indicator {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .led {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    display: inline-block;
  }

  .led.green {
    background-color: var(--color-success);
    box-shadow: 0 0 8px rgba(16, 185, 129, 0.6);
  }

  .led.red {
    background-color: #ef4444;
    box-shadow: 0 0 8px rgba(239, 68, 68, 0.6);
  }

  .text-right {
    text-align: right;
  }

  .status-banner {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 14px;
    border-radius: 8px;
    font-size: 0.82rem;
    margin-top: 0.5rem;
    font-weight: 500;
  }

  .success-banner {
    background-color: var(--color-success-bg);
    color: var(--color-success);
    border: 1px solid rgba(16, 185, 129, 0.2);
  }

  .error-banner {
    background-color: rgba(239, 68, 68, 0.1);
    color: #f87171;
    border: 1px solid rgba(239, 68, 68, 0.2);
  }

  .banner-icon {
    flex-shrink: 0;
  }

  /* --- OTHER PAGES CONTAINER --- */
  .other-view-container {
    padding: 2rem;
    flex-grow: 1;
    overflow-y: auto;
  }

  .section-subtitle {
    font-size: 0.88rem;
    color: var(--text-muted);
    margin-bottom: 1.5rem;
  }

  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 4rem 2rem;
    color: var(--text-muted);
    gap: 1rem;
    font-size: 0.95rem;
  }

  .history-list {
    display: flex;
    flex-direction: column;
    gap: 1.25rem;
  }

  .history-item-row {
    border-bottom: 1px solid var(--border-light);
    padding-bottom: 1.25rem;
  }

  .history-item-row:last-child {
    border-bottom: none;
  }

  .history-meta {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 6px;
  }

  .history-time {
    font-size: 0.78rem;
    color: var(--text-muted);
  }

  .reload-btn {
    background: none;
    border: 1px solid var(--border-light);
    color: var(--color-accent);
    font-size: 0.78rem;
    padding: 4px 8px;
    border-radius: 4px;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 4px;
    transition: background-color var(--transition-fast);
  }

  .reload-btn:hover {
    background-color: rgba(89, 255, 0, 0.08);
  }

  .history-content strong {
    font-size: 0.95rem;
    color: var(--text-primary);
    display: block;
    margin-bottom: 4px;
  }

  .history-content p {
    font-size: 0.88rem;
    color: var(--text-secondary);
    line-height: 1.4;
  }

  .transcript-quote {
    font-size: 0.9rem;
    font-style: italic;
    color: var(--text-secondary);
    border-left: 3px solid var(--border-light);
    padding-left: 10px;
    margin-top: 6px;
  }

  /* --- DATA SOURCE LISTINGS --- */
  .listings-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 1rem;
    margin-bottom: 2rem;
  }

  .listing-item-card {
    padding: 1.25rem;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .listing-header-main {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 8px;
  }

  .listing-header-main h4 {
    font-size: 0.95rem;
    color: var(--text-primary);
  }



  /* --- UTILITY SPINNER --- */
  .spinner {
    width: 14px;
    height: 14px;
    border: 2px solid rgba(255, 255, 255, 0.25);
    border-top: 2px solid #ffffff;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
  }



  .mini-spinner {
    width: 14px;
    height: 14px;
    border: 2px solid rgba(89, 255, 0, 0.25);
    border-top: 2px solid var(--color-accent);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  .empty-conversation {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 4rem 1.5rem;
    text-align: center;
    color: var(--text-muted);
  }

  .empty-convo-icon {
    background: rgba(89, 255, 0, 0.1);
    color: var(--color-accent);
    padding: 1rem;
    border-radius: 50%;
    margin-bottom: 1.25rem;
  }

  .empty-conversation h4 {
    color: var(--text-primary);
    margin-bottom: 0.5rem;
    font-size: 1.15rem;
  }

  .empty-conversation p {
    font-size: 0.88rem;
    max-width: 440px;
    line-height: 1.5;
    margin-bottom: 1.75rem;
  }

  .empty-convo-suggestions {
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
    align-items: center;
    width: 100%;
    max-width: 340px;
  }

  .empty-convo-suggestions button {
    width: 100%;
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid var(--border-light);
    border-radius: 8px;
    padding: 10px 14px;
    color: var(--text-secondary);
    font-size: 0.82rem;
    font-family: var(--font-body);
    cursor: pointer;
    text-align: left;
    transition: background-color var(--transition-fast), border-color var(--transition-fast), color var(--transition-fast);
  }

  .light-theme .empty-convo-suggestions button {
    background: #ffffff;
  }

  .empty-convo-suggestions button:hover {
    background: rgba(89, 255, 0, 0.05);
    border-color: var(--color-accent);
    color: var(--color-accent);
  }

  .mobile-menu-btn {
    display: none;
  }

  .mobile-close-btn {
    display: none;
  }

  .mobile-backdrop {
    display: none;
  }

  .header-left {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  /* ==========================================================================
     RESPONSIVE & ADAPTIVE STYLES FOR ALL SCREEN DEVICES
     ========================================================================== */

  /* Mobile Devices (< 768px) */
  @media (max-width: 767px) {
    .dashboard-container {
      flex-direction: column;
      height: 100vh;
      height: 100dvh;
      width: 100vw;
      overflow: hidden;
    }

    .mobile-menu-btn {
      display: flex;
    }

    .mobile-backdrop {
      display: block;
      position: fixed;
      inset: 0;
      background: rgba(6, 9, 19, 0.7);
      backdrop-filter: blur(6px);
      -webkit-backdrop-filter: blur(6px);
      z-index: 99;
      border: none;
      padding: 0;
      cursor: pointer;
    }

    .sidebar {
      position: fixed;
      top: 0;
      left: 0;
      bottom: 0;
      width: 270px !important;
      height: 100%;
      z-index: 100;
      transform: translateX(-100%);
      transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
      box-shadow: 0 0 30px rgba(0, 0, 0, 0.6);
      border-right: 1px solid var(--border-light);
      padding: 1.25rem 1rem;
      background-color: var(--bg-secondary);
    }

    .sidebar.mobile-open {
      transform: translateX(0);
    }

    .sidebar-top {
      display: flex;
      flex-direction: column;
      gap: 1.5rem;
    }

    .logo-box {
      width: 100%;
      justify-content: space-between;
    }

    .logo-text {
      display: block;
    }

    .mobile-close-btn {
      display: flex;
      align-items: center;
      justify-content: center;
      margin-left: auto;
    }

    .sidebar-menu {
      display: flex;
      flex-direction: column;
      gap: 0.5rem;
    }

    .menu-item {
      padding: 12px 14px;
      font-size: 0.95rem;
      border-radius: 8px;
      width: 100%;
    }

    .collapse-btn {
      display: none;
    }

    .workspace {
      width: 100%;
      height: 100%;
      flex-grow: 1;
      overflow: hidden;
    }

    .workspace-header {
      padding: 0 0.85rem;
      height: 56px;
    }

    .workspace-header h1 {
      font-size: 1rem;
    }

    .workspace-content {
      padding: 0.75rem;
      overflow-y: auto;
    }

    .chat-bubble-container {
      max-width: 94%;
    }

    .bubble-text {
      padding: 0.45rem 0.75rem;
      font-size: 0.86rem;
      overflow-wrap: anywhere;
      word-break: break-word;
    }

    .quick-ask-body {
      padding: 0.85rem;
    }

    .quick-ask-footer {
      flex-direction: row;
      align-items: center;
    }

    .action-buttons-group {
      width: 100%;
      display: flex;
      gap: 0.5rem;
    }

    .voice-btn {
      flex-shrink: 0;
      width: 34px !important;
      height: 34px !important;
      min-height: 34px !important;
      min-width: 34px !important;
      padding: 0;
    }

    .send-btn {
      flex-grow: 1;
      min-height: 34px !important;
      height: 34px !important;
    }
  }

  /* Tablet Devices (768px - 1024px) */
  @media (min-width: 768px) and (max-width: 1024px) {
    .sidebar {
      width: 200px;
    }

    .sidebar.collapsed {
      width: 68px;
    }

    .workspace-header {
      padding: 0 1.25rem;
    }

    .workspace-content {
      padding: 1rem;
    }

    .chat-bubble-container {
      max-width: 88%;
    }

    .bubble-text {
      overflow-wrap: anywhere;
      word-break: break-word;
    }
  }
</style>
