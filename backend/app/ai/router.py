"""
ai/router.py
────────────
Intelligent Query & Intent Router for Real Estate AI Assistant.
Analyzes user questions to determine the optimal execution pipeline:
  • REAL_ESTATE_SEARCH  → Atlas Hybrid Search RAG + LangChain Agent
  • FINANCIAL_CALCULATOR → Direct MCP EMI & Pricing Calculator Tools
  • MAPS_AND_LOCATION   → Direct MCP Google Maps & Routes Navigation
  • SCHEDULE_SITE_VISIT → Direct MCP Calendar & Site Visit Tools
  • GENERAL_CONVERSATION → Lightweight direct conversational response (skips heavy DB search)
"""

import re
from typing import Dict, Any, List, Optional
from enum import Enum


class QueryIntent(str, Enum):
    REAL_ESTATE_SEARCH = "REAL_ESTATE_SEARCH"
    FINANCIAL_CALCULATOR = "FINANCIAL_CALCULATOR"
    MAPS_AND_LOCATION = "MAPS_AND_LOCATION"
    SCHEDULE_SITE_VISIT = "SCHEDULE_SITE_VISIT"
    GENERAL_CONVERSATION = "GENERAL_CONVERSATION"


# ── Pattern Matchers for Fast Classification (<2ms) ──

CALCULATOR_PATTERNS = [
    r'\bemi\b', r'\bhome loan\b', r'\bloan eligibility\b', r'\binterest rate\b',
    r'\bstamp duty\b', r'\bregistration fee\b', r'\bdown payment\b', r'\bmonthly installment\b',
    r'\bcalculate.*loan\b', r'\bcalculate.*emi\b', r'\bhow much emi\b', r'\baffordability\b'
]

MAPS_PATTERNS = [
    r'\bhow far\b', r'\bdistance between\b', r'\bdistance from\b', r'\broute to\b',
    r'\bdirections? to\b', r'\bhow to reach\b', r'\btravel time\b', r'\bdriving duration\b',
    r'\bnearby (metro|hospital|school|it park|mall|restaurant|supermarket)\b',
    r'\bamenities near\b', r'\blocated near\b', r'\blatitude.*longitude\b'
]

CALENDAR_PATTERNS = [
    r'\bbook.*(visit|tour|appointment|slot)\b', r'\bschedule.*(visit|tour|meeting|call)\b',
    r'\bsite visit\b', r'\bproperty tour\b', r'\bavailable slots?\b',
    r'\bmy bookings?\b', r'\bmy visits?\b', r'\bcancel.*visit\b', r'\breschedule.*visit\b'
]

GREETING_PATTERNS = [
    r'^(hi|hello|hey|vanakkam|namaste|good (morning|afternoon|evening)|hola)\b',
    r'^(who are you|what can you do|how can you help|help me|introduce yourself)\b',
    r'^(thanks|thank you|nandri|ok|okay|bye|goodbye)\b'
]

SEARCH_KEYWORDS = [
    r'\b\d+\s*bhk\b', r'\bflats?\b', r'\bapartments?\b', r'\bvillas?\b', r'\bhouses?\b',
    r'\bplots?\b', r'\bbudget\b', r'\blakhs?\b', r'\bcrores?\b', r'\bprice\b',
    r'\bsqft\b', r'\bsquare feet\b', r'\bfor sale\b', r'\bproperties\b',
    r'\bprestige\b', r'\bcasagrand\b', r'\bappaswamy\b', r'\bhiranandani\b',
    r'\bomr\b', r'\bvelachery\b', r'\bt nagar\b', r'\banna nagar\b', r'\badayar\b',
    r'\bporur\b', r'\bguindy\b', r'\bsholinganallur\b', r'\bperungudi\b', r'\bmedavakkam\b'
]


def classify_query_intent(
    query: str,
    history: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Classifies the user query into a QueryIntent with high precision.
    Returns:
        {
            "intent": QueryIntent,
            "requires_rag": bool,
            "confidence": float,
            "extracted_entities": dict
        }
    """
    cleaned_q = query.strip().lower()
    
    # 1. Check Greetings / Chit-chat
    for pat in GREETING_PATTERNS:
        if re.search(pat, cleaned_q):
            # If greeting also mentions property specifics, treat as property search
            if not any(re.search(sp, cleaned_q) for sp in SEARCH_KEYWORDS[:10]):
                return {
                    "intent": QueryIntent.GENERAL_CONVERSATION,
                    "requires_rag": False,
                    "confidence": 0.95,
                    "extracted_entities": {}
                }

    # 2. Check Real Estate Search intent FIRST if explicit search keywords are present
    # This ensures compound queries like "Find 2 BHK properties in Velachery and show driving distance from Porur"
    # properly trigger RAG retrieval for properties.
    has_search_keywords = any(re.search(sp, cleaned_q) for sp in SEARCH_KEYWORDS)
    if has_search_keywords:
        return {
            "intent": QueryIntent.REAL_ESTATE_SEARCH,
            "requires_rag": True,
            "confidence": 0.95,
            "extracted_entities": {}
        }

    # 3. Check Site Visit & Calendar intent
    for pat in CALENDAR_PATTERNS:
        if re.search(pat, cleaned_q):
            return {
                "intent": QueryIntent.SCHEDULE_SITE_VISIT,
                "requires_rag": False,
                "confidence": 0.92,
                "extracted_entities": {}
            }

    # 4. Check Financial / EMI intent
    for pat in CALCULATOR_PATTERNS:
        if re.search(pat, cleaned_q):
            return {
                "intent": QueryIntent.FINANCIAL_CALCULATOR,
                "requires_rag": False,
                "confidence": 0.90,
                "extracted_entities": {}
            }

    # 5. Check Maps & Navigation intent
    for pat in MAPS_PATTERNS:
        if re.search(pat, cleaned_q):
            return {
                "intent": QueryIntent.MAPS_AND_LOCATION,
                "requires_rag": False,
                "confidence": 0.90,
                "extracted_entities": {}
            }

    # Default fallback: If conversation history exists, it might be a context follow-up property question
    if history and len(history) > 0:
        return {
            "intent": QueryIntent.REAL_ESTATE_SEARCH,
            "requires_rag": True,
            "confidence": 0.75,
            "extracted_entities": {}
        }

    # General fallback
    return {
        "intent": QueryIntent.REAL_ESTATE_SEARCH,
        "requires_rag": True,
        "confidence": 0.60,
        "extracted_entities": {}
    }
