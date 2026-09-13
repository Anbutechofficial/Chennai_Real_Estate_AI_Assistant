import os
import asyncio
import requests
from fastapi import APIRouter, HTTPException, UploadFile, File

from app.core.models import QuestionRequest
from app.core.config import Setting
from app.rag.retrieval import retrieve
from app.ai.prompt import build_prompt, check_query_safety
from app.ai.chatservice import ask_llm, ask_agent
from app.ai.router import classify_query_intent, QueryIntent

router = APIRouter()

_ask_response_cache: dict[str, dict] = {}
MAX_RESPONSE_CACHE_SIZE = 300


import re

def sanitize_answer(answer: str) -> str:
    if not answer:
        return answer
    
    # Remove any stray [METADATA] header lines if leaked
    cleaned = re.sub(r'\[METADATA\][^\n]*\n?', '', answer, flags=re.IGNORECASE)
    
    # Strip introductory matching count lines and top matching properties header lines
    cleaned = re.sub(r'(?:We found|There are)\s+\d+\s+matching properties[^\n]*\n?', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'Here are the top \d+ matching properties:?\n?', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'(?:Total matching properties|Matching properties count)(?: found)?:?\s*\d*\.?\n?', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'(?:Matching_Count|matching_count):\s*\d+\.?\n?', '', cleaned, flags=re.IGNORECASE)
    
    # Transform raw snake_case technical values into elegant human phrasing if any remain
    cleaned = re.sub(r'(?:Average_Property_Price|average_price):\s*(?:Rs\s*)?([\d\.]+)\s*(?:Lakhs)?', r'The average property price is Rs \1 Lakhs.', cleaned, flags=re.IGNORECASE)
    
    # Clean up residual snake_case keys if any remain
    cleaned = cleaned.replace("Average_Property_Price:", "Average Property Price:")
    cleaned = cleaned.replace("Matching_Count:", "")
    cleaned = cleaned.replace("Exact_Match_Found:", "")
    cleaned = cleaned.replace("exact_match_found:", "")
    cleaned = cleaned.replace("total_database_listings:", "")

    return cleaned.strip()


@router.post("/ask")
async def ask(request: QuestionRequest):
    # Step 0: Security & Safety Check (Block prompt injections & malicious prompts)
    is_safe, default_reply = check_query_safety(request.question)
    if is_safe == False:
        res = {
            "question": request.question,
            "answer": default_reply,
            "intent": "BLOCKED"
        }
        return res


    # Step 1: Intelligent Intent & Query Routing
    classification = classify_query_intent(request.question, history=request.history)
    intent = classification["intent"]
    requires_rag = classification["requires_rag"]

    # Step 2: Dynamic Context Resolution based on Routed Intent
    if requires_rag:
        # Atlas Hybrid Search RAG + Property Filters
        retrieved_docs = await retrieve(request.question, history=request.history)
        prompt = build_prompt(request.question, retrieved_docs)
    else:
        # Direct Tool / Fast Conversational Path — Bypass DB RAG overhead
        prompt = request.question

    # Step 3: Get LLM Response asynchronously with agentic tool calling (Google Maps, EMI, Search, Bookings)
    try:
        raw_answer = await ask_agent(
            user_query=request.question,
            history=request.history,
            context_prompt=prompt
        )
        answer = sanitize_answer(raw_answer)
    except Exception as e:
        print(f"[Assistant Router] Falling back to direct LLM due to: {e}")
        try:
            raw_answer = await ask_llm(prompt)
            answer = sanitize_answer(raw_answer)
        except Exception as direct_e:
            raise HTTPException(status_code=500, detail=str(direct_e))

    result = {
        "question": request.question,
        "answer": answer,
        "intent": intent.value if hasattr(intent, "value") else str(intent)
    }

    # Step 4: Return Response
    return result



# -------------------------
# Transcribe Route
# -------------------------
@router.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    audio_data = await file.read()
    if not audio_data or len(audio_data) < 100:
        return {"text": ""}

    raw_content_type = file.content_type or "audio/webm"
    clean_mime_type = raw_content_type.split(";")[0].strip().lower()
    if not clean_mime_type or clean_mime_type == "application/octet-stream":
        clean_mime_type = "audio/webm"

    gemini_api_key = getattr(Setting, "GEMINI_API_KEY", "") or os.getenv("GEMINI_API_KEY", "")

    # Primary Audio Transcription: Gemini 2.5 Flash Multimodal
    if gemini_api_key:
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=gemini_api_key)
            audio_part = types.Part.from_bytes(
                data=audio_data,
                mime_type=clean_mime_type
            )
            prompt = (
                "Transcribe spoken speech strictly in English or Tanglish (Tamil words written using English/Latin alphabet, e.g. '3 BHK flat in Egmore'). "
                "Output ONLY the transcribed text without any preamble, explanation, quotes, or markdown tags."
            )

            def _call_gemini():
                for m in ["gemini-flash-latest", "gemini-2.5-flash", "gemini-flash-lite-latest", "gemini-2.5-flash-lite"]:
                    try:
                        return client.models.generate_content(
                            model=m,
                            contents=[audio_part, prompt]
                        )
                    except Exception:
                        continue
                return None

            res = await asyncio.to_thread(_call_gemini)
            if res and hasattr(res, "text") and res.text:
                text = res.text.strip()
                if text:
                    return {"text": text, "provider": "gemini"}
        except Exception as e:
            print(f"Gemini audio transcription error: {e}")

    return {"text": "", "error": "Transcription failed."}

    # Return empty text gracefully if audio is silent or unparseable
    return {"text": ""}

