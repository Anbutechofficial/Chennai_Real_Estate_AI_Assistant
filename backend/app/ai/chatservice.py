import os
import re
import json
import asyncio
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    AIMessage,
    SystemMessage,
    ToolMessage
)
from langchain_google_genai import ChatGoogleGenerativeAI

import litellm
litellm.suppress_debug_info = True
os.environ["LITELLM_LOG"] = "ERROR"

from app.core.config import Setting
from app.ai.tools import get_langchain_tools
from app.ai.prompt import AGENT_SYSTEM_PROMPT

load_dotenv()

# Pre-cache tool lookup dictionary for fast resolution
_TOOLS_LIST = get_langchain_tools()
_TOOLS_BY_NAME = {t.name: t for t in _TOOLS_LIST}


def _extract_text_content(content: Any) -> str:
    """Extracts clean text string from LangChain message content."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts = []
        for part in content:
            if isinstance(part, dict):
                if part.get("type") == "text":
                    text_parts.append(part.get("text", ""))
                elif "text" in part:
                    text_parts.append(str(part["text"]))
            elif isinstance(part, str):
                text_parts.append(part)
        return " ".join(text_parts).strip()
    return str(content or "").strip()


def get_langchain_llm(model_name: str = "gemini-3.6-flash", temperature: float = 0.2):
    """Creates a configured ChatGoogleGenerativeAI instance if key is valid."""
    gemini_key = getattr(Setting, "GEMINI_API_KEY", "") or os.getenv("GEMINI_API_KEY", "")
    if not gemini_key or not gemini_key.strip():
        raise ValueError("Valid Google AI Studio GEMINI_API_KEY is not configured.")

    return ChatGoogleGenerativeAI(
        model=model_name,
        api_key=gemini_key.strip(),
        temperature=temperature,
        timeout=25
    )


def get_llm_with_fallbacks(temperature: float = 0.2):
    """Returns primary ChatGoogleGenerativeAI model chained with fallback models if key is valid."""
    primary_model = get_langchain_llm("gemini-3.6-flash", temperature=temperature)
    fallback_model_1 = get_langchain_llm("gemini-3.5-flash-lite", temperature=temperature)

    return primary_model.with_fallbacks([fallback_model_1])


async def generate_with_gemini(
    prompt: str,
    history: Optional[List[Dict[str, Any]]] = None,
    system_prompt: str = AGENT_SYSTEM_PROMPT
) -> Optional[str]:
    """Fast, direct execution with Google GenAI SDK using gemini-3.5-flash / gemini-3.5-flash-lite."""
    gemini_key = getattr(Setting, "GEMINI_API_KEY", "") or os.getenv("GEMINI_API_KEY", "")
    if not gemini_key or not gemini_key.strip():
        return None
    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=gemini_key.strip())

        conversation_context = []
        if history:
            for msg in history[-6:]:
                role = msg.get("role") or msg.get("sender") or "user"
                content = msg.get("content") or msg.get("text") or ""
                if content.strip():
                    conversation_context.append(f"{role.capitalize()}: {content.strip()}")

        context_str = "\n".join(conversation_context) if conversation_context else ""
        history_header = f"CONVERSATION HISTORY:\n{context_str}\n\n" if context_str else ""
        user_content = f"{history_header}CURRENT USER QUERY / CONTEXT:\n{prompt}"

        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.2
        )

        for model_choice in ["gemini-flash-latest", "gemini-2.5-flash", "gemini-flash-lite-latest", "gemini-2.5-flash-lite", "gemini-2.5-pro", "gemini-3.6-flash"]:
            try:
                res = await asyncio.to_thread(
                    client.models.generate_content,
                    model=model_choice,
                    contents=user_content,
                    config=config
                )
                if res and hasattr(res, "text") and res.text and len(res.text.strip()) > 10:
                    return res.text.strip()
            except Exception as model_err:
                print(f"[Gemini {model_choice}] note: {model_err}")
    except Exception as e:
        print(f"[Gemini Provider] note: {e}")
    return None


async def _resolve_direct_mcp_tool_context(user_query: str) -> Optional[str]:
    """
    Direct MCP tool dispatcher fallback: Extracts entities from query and runs
    the relevant tool directly so LLM always receives verified factual data.
    """
    q_lower = user_query.lower().strip()
    import re
    from app.ai.mcp.location_service import calculate_route_and_distance, get_nearby_places, KNOWN_COORDINATES
    from app.ai.mcp.calculator_service import calculate_home_loan_emi, calculate_property_price_breakdown
    from app.ai.mcp.calendar_service import check_site_visit_availability

    # 1. Distance & Route calculation
    is_route_query = any(kw in q_lower for kw in [
        "distance", "how far", "travel time", "driving time", "route", "duration",
        "directions", "how to reach", "driving distance", "from my location", "by car"
    ])
    if is_route_query:
        origin = None
        destination = None

        # Pattern A: "how far is <dest> from <origin>"
        mA = re.search(r'how far is\s+([^,]+?)\s+(?:from|to)\s+([^?]+)', q_lower)
        if mA:
            destination = mA.group(1).replace("by car", "").strip()
            origin = mA.group(2).replace("by car", "").strip()

        # Pattern B: "distance/route from <orig> to <dest>" or "between <orig> and <dest>"
        if not (origin and destination):
            mB = re.search(r'(?:distance|travel time|route).*?(?:from|between)\s+([^,]+?)\s+(?:to|and)\s+([^?]+)', q_lower)
            if mB:
                origin = mB.group(1).strip()
                destination = mB.group(2).replace("?", "").replace("and what is the driving duration", "").strip()

        # Pattern C: "I am (currently) at/in <orig> ... in/to <dest>"
        if not (origin and destination):
            mC = re.search(r'(?:i am|currently|location is|from)\s+(?:currently\s+)?(?:at|in|from)?\s*([a-zA-Z\s]+?)(?:[.,;]|\band\b|\bfind\b|\bshow\b|\bhow far\b|\bwhat is\b)', q_lower)
            if mC:
                cand_origin = mC.group(1).strip()
                cand_origin = re.sub(r'^(at|in|from)\s+', '', cand_origin).strip()
                if cand_origin:
                    origin = cand_origin

            m_dest = re.search(r'(?:in|to|reach|destination)\s+([a-zA-Z\s]+?)(?:[.,;]|\band\b|\bfrom\b|\bfor\b|\bwith\b|\bshow\b|\?)', q_lower)
            if m_dest:
                cand_dest = m_dest.group(1).strip()
                cand_dest = re.sub(r'^(in|to)\s+', '', cand_dest).strip()
                if cand_dest and cand_dest != origin:
                    destination = cand_dest

        # Pattern D: Locality scanner across known Chennai coordinates
        if not (origin and destination):
            found_localities = []
            for loc in sorted(KNOWN_COORDINATES.keys(), key=len, reverse=True):
                if re.search(r'\b' + re.escape(loc) + r'\b', q_lower):
                    if loc not in found_localities:
                        found_localities.append(loc)
            if len(found_localities) >= 2:
                loc1, loc2 = found_localities[0], found_localities[1]
                idx1 = q_lower.find(loc1)
                idx2 = q_lower.find(loc2)
                if idx1 < idx2:
                    origin = origin or loc1.title()
                    destination = destination or loc2.title()
                else:
                    origin = origin or loc2.title()
                    destination = destination or loc1.title()
            elif len(found_localities) == 1:
                if not destination and origin != found_localities[0].title():
                    destination = found_localities[0].title()
                elif not origin and destination != found_localities[0].title():
                    origin = found_localities[0].title()

        if origin and destination:
            try:
                route_res = await calculate_route_and_distance(origin=origin, destination=destination)
                if route_res.get("status") == "SUCCESS":
                    road_km = route_res.get('road_distance_km')
                    drive_mins = route_res.get('driving_time_mins')
                    steps = route_res.get('key_steps', [])
                    steps_text = "\n  - ".join(steps) if steps else "Direct arterial route"
                    return (
                        f"\n[LIVE MCP GOOGLE MAPS & NAVIGATION RESULT]:\n"
                        f"Origin: {route_res.get('origin')}\n"
                        f"Destination: {route_res.get('destination')}\n"
                        f"Road Distance: {road_km} km\n"
                        f"Estimated Driving Duration: {drive_mins} mins\n"
                        f"Route Summary: {route_res.get('route_summary')}\n"
                        f"Key Corridor Steps:\n  - {steps_text}\n"
                        f"Google Maps Navigation URL: {route_res.get('google_maps_url')}\n"
                        f"Google Maps Link Markdown: {route_res.get('google_maps_link')}\n"
                        f"Embedded Map Markdown: {route_res.get('embedded_map_markdown')}\n"
                    )
            except Exception as e:
                print(f"[Direct MCP Location Error]: {e}")

    # 2. Site Visit Available Slots
    if any(w in q_lower for w in ["site visit", "available slots", "visit slots", "book slot", "slots for"]):
        prop_name = "Prestige Courtyards"
        known_projects = ["prestige courtyards", "casagrand zenith", "appaswamy", "hiranandani", "t nagar", "omr", "velachery"]
        for kp in known_projects:
            if kp in q_lower:
                prop_name = kp.title()
                break
        date_str = "Tomorrow" if "tomorrow" in q_lower else ("This Weekend" if "weekend" in q_lower or "saturday" in q_lower or "sunday" in q_lower else "Upcoming Date")
        try:
            slots_res = await check_site_visit_availability(property_name=prop_name, preferred_date=date_str)
            return (
                f"\n[LIVE MCP CALENDAR AVAILABILITY RESULT]:\n"
                f"Property: {slots_res.get('property_name')}\n"
                f"Requested Date: {slots_res.get('date')}\n"
                f"Available Slots: {', '.join(slots_res.get('available_slots', []))}\n"
                f"Already Booked Slots: {', '.join(slots_res.get('booked_slots', [])) if slots_res.get('booked_slots') else 'None'}\n"
                f"Recommended Time Slot: {slots_res.get('recommended_slot')}\n"
            )
        except Exception:
            pass

    # 3. EMI & Loan calculation
    if "emi" in q_lower or "home loan" in q_lower or "calculate" in q_lower:
        amount_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:lakhs?|lacs?|cr|crore?)', q_lower)
        if amount_match:
            val = float(amount_match.group(1))
            if "cr" in q_lower or "crore" in q_lower:
                val = val * 100
            rate_match = re.search(r'(\d+(?:\.\d+)?)\s*%', q_lower)
            rate = float(rate_match.group(1)) if rate_match else 8.5
            tenure_match = re.search(r'(\d+)\s*(?:years?|yrs?)', q_lower)
            tenure = int(tenure_match.group(1)) if tenure_match else 20
            try:
                emi_res = calculate_home_loan_emi(loan_amount_lakhs=val, annual_interest_rate=rate, tenure_years=tenure)
                return (
                    f"\n[LIVE MCP FINANCIAL EMI RESULT]:\n"
                    f"Loan Amount: Rs {val} Lakhs\n"
                    f"Interest Rate: {rate}%\n"
                    f"Tenure: {tenure} Years\n"
                    f"Monthly EMI: Rs {emi_res.get('monthly_emi_formatted')}\n"
                    f"Total Interest Payable: Rs {emi_res.get('total_interest_lakhs')} Lakhs\n"
                    f"Total Amount Payable: Rs {emi_res.get('total_payment_lakhs')} Lakhs\n"
                )
            except Exception:
                pass

    return None


def _build_langchain_messages(
    user_query: str,
    history: Optional[List[Dict[str, Any]]] = None,
    context_prompt: Optional[str] = None
) -> List[BaseMessage]:
    """Converts raw conversation history and context into LangChain message objects."""
    messages: List[BaseMessage] = [SystemMessage(content=AGENT_SYSTEM_PROMPT)]

    if history:
        for msg in history[-6:]:
            role = msg.get("role") or msg.get("sender") or "user"
            content = msg.get("content") or msg.get("text") or ""
            if content.strip():
                if role in ["assistant", "ai", "bot"]:
                    messages.append(AIMessage(content=content))
                else:
                    messages.append(HumanMessage(content=content))

    final_user_msg = context_prompt if context_prompt else user_query
    messages.append(HumanMessage(content=final_user_msg))
    return messages


async def _intercept_and_execute_raw_tool_calls(raw_text: str, user_query: str) -> str:
    """
    Detects if an LLM returned raw tool JSON or functional tool calls,
    executes the underlying tools directly, and synthesizes a complete,
    human-readable final answer with properties, routes, maps, and calculations.
    """
    if not raw_text or not raw_text.strip():
        return raw_text

    text = raw_text.strip()
    tool_calls = []

    # 1. Parse JSON candidate (array or object)
    json_candidate = None
    if "```json" in text:
        m = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
        if m:
            json_candidate = m.group(1).strip()
    elif (text.startswith("[") and text.endswith("]")) or (text.startswith("{") and text.endswith("}")):
        json_candidate = text

    if json_candidate:
        try:
            parsed = json.loads(json_candidate)
            if isinstance(parsed, list):
                for item in parsed:
                    if isinstance(item, dict) and ("tool" in item or "function" in item or "name" in item):
                        t_name = item.get("tool") or item.get("function") or item.get("name")
                        t_params = item.get("parameters") or item.get("arguments") or item.get("args") or {}
                        tool_calls.append((t_name, t_params))
            elif isinstance(parsed, dict) and ("tool" in parsed or "function" in parsed or "name" in parsed):
                t_name = parsed.get("tool") or parsed.get("function") or parsed.get("name")
                t_params = parsed.get("parameters") or parsed.get("arguments") or parsed.get("args") or {}
                tool_calls.append((t_name, t_params))
        except Exception:
            pass

    # 2. Parse functional syntax, e.g.: calculate_distance_and_route(...) or search_properties(...)
    if not tool_calls:
        fn_matches = re.findall(
            r'(\b(?:calculate_distance_and_route|search_properties|calculate_emi|calc_home_loan_emi|calculate_property_price_breakdown|find_nearby_amenities|check_site_visit_availability|schedule_site_visit)\b)\s*\((.*?)\)',
            text,
            re.DOTALL
        )
        if fn_matches:
            for fn_name, fn_args_str in fn_matches:
                params = {}
                for param_match in re.finditer(r'([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|([^,\s\)]+))', fn_args_str):
                    k = param_match.group(1)
                    v = param_match.group(2) or param_match.group(3) or param_match.group(4)
                    if v:
                        v_str = str(v).strip()
                        try:
                            if "." in v_str:
                                v = float(v_str)
                            else:
                                v = int(v_str)
                        except ValueError:
                            v = v_str
                    params[k] = v
                tool_calls.append((fn_name, params))

    if not tool_calls:
        return text

    # 3. Execute detected tools!
    from app.ai.mcp.location_service import calculate_route_and_distance, get_nearby_places
    from app.ai.mcp.calculator_service import calculate_home_loan_emi, calculate_property_price_breakdown
    from app.rag.retrieval import retrieve

    results_parts = []
    properties_formatted = []
    route_formatted = ""

    for fn_name, params in tool_calls:
        fn_clean = str(fn_name).lower().strip()
        if "search_properties" in fn_clean:
            loc = params.get("location", "")
            bhk = params.get("bhk", "")
            max_price = params.get("max_price", "")
            q_parts = []
            if bhk:
                q_parts.append(f"{bhk} BHK")
            if loc:
                q_parts.append(f"in {loc}")
            if max_price:
                q_parts.append(f"under {max_price} Lakhs")
            search_str = " ".join(q_parts) if q_parts else user_query
            try:
                docs = await retrieve(search_str, top_k=5)
                prop_idx = 1
                for d in docs:
                    p_text = d.get("text", "") if isinstance(d, dict) else str(d)
                    if p_text.startswith("[METADATA]"):
                        continue
                    properties_formatted.append(f"Property {prop_idx}\n{p_text}")
                    prop_idx += 1
            except Exception as e:
                print(f"[Tool Interceptor RAG Error]: {e}")

        elif "distance" in fn_clean or "route" in fn_clean:
            origin = params.get("origin", "")
            dest = params.get("destination", "")
            if origin and dest:
                try:
                    res = await calculate_route_and_distance(origin=origin, destination=dest)
                    if res.get("status") == "SUCCESS":
                        road_km = res.get("road_distance_km")
                        drive_mins = res.get("driving_time_mins")
                        route_summary = res.get("route_summary")
                        key_steps = res.get("key_steps", [])
                        steps_md = "\n".join([f"- {s}" for s in key_steps]) if key_steps else f"- Direct arterial route from {origin} to {dest}"
                        google_link = res.get("google_maps_link", "")
                        map_img = res.get("embedded_map_markdown", "")
                        route_formatted = (
                            f"### 📍 Driving Distance & Route ({origin} ➔ {dest})\n"
                            f"- **Road Distance:** {road_km} km\n"
                            f"- **Driving Travel Time:** ~{drive_mins} minutes\n"
                            f"- **Route Summary:** {route_summary}\n\n"
                            f"**Key Corridor Directions:**\n"
                            f"{steps_md}\n\n"
                            f"{map_img}\n\n"
                            f"{google_link}"
                        )
                except Exception as e:
                    print(f"[Tool Interceptor Distance Error]: {e}")

        elif "emi" in fn_clean:
            try:
                amount = float(params.get("loan_amount_lakhs") or params.get("amount") or 50)
                rate = float(params.get("annual_interest_rate") or params.get("interest_rate") or 8.5)
                tenure = int(params.get("tenure_years") or params.get("tenure") or 20)
                emi_res = calculate_home_loan_emi(loan_amount_lakhs=amount, annual_interest_rate=rate, tenure_years=tenure)
                results_parts.append(
                    f"### 🧮 Home Loan EMI Calculation\n"
                    f"- **Loan Amount:** Rs {amount} Lakhs\n"
                    f"- **Interest Rate:** {rate}%\n"
                    f"- **Tenure:** {tenure} Years\n"
                    f"- **Monthly EMI:** Rs {emi_res.get('monthly_emi_formatted')}\n"
                    f"- **Total Interest Payable:** Rs {emi_res.get('total_interest_lakhs')} Lakhs\n"
                    f"- **Total Repayment Amount:** Rs {emi_res.get('total_payment_lakhs')} Lakhs"
                )
            except Exception as e:
                print(f"[Tool Interceptor EMI Error]: {e}")

        elif "price_breakdown" in fn_clean:
            try:
                base = float(params.get("base_price_lakhs") or 75)
                sqft = float(params.get("sqft") or 1000)
                pb_res = calculate_property_price_breakdown(base_price_lakhs=base, sqft=sqft)
                results_parts.append(
                    f"### 🧮 Property Price & Registration Breakdown\n"
                    f"- **Base Price:** Rs {base} Lakhs\n"
                    f"- **Stamp Duty (2%):** Rs {pb_res.get('stamp_duty_lakhs')} Lakhs\n"
                    f"- **Registration (7%):** Rs {pb_res.get('registration_lakhs')} Lakhs\n"
                    f"- **All-Inclusive On-Road Cost:** Rs {pb_res.get('total_cost_lakhs')} Lakhs"
                )
            except Exception as e:
                print(f"[Tool Interceptor Price Breakdown Error]: {e}")

        elif "amenities" in fn_clean:
            try:
                loc = params.get("location", "Chennai")
                a_type = params.get("amenity_type", "metro")
                am_res = await get_nearby_places(location=loc, amenity_type=a_type)
                items_str = "\n".join([f"- **{it['name']}** ({it['category']}): {it['distance_km']} km | [📍 View on Google Maps]({it['google_maps_url']})" for it in am_res[:5]])
                results_parts.append(f"### 📍 Nearby Amenities in {loc.title()}\n{items_str}")
            except Exception as e:
                print(f"[Tool Interceptor Amenities Error]: {e}")

    final_blocks = []
    if properties_formatted:
        final_blocks.append("\n\n".join(properties_formatted[:5]))
    if route_formatted:
        final_blocks.append(route_formatted)
    if results_parts:
        final_blocks.append("\n\n".join(results_parts))

    if final_blocks:
        return "\n\n---\n\n".join(final_blocks)

    return text


async def ask_agent(
    user_query: str,
    history: Optional[List[Dict[str, Any]]] = None,
    context_prompt: Optional[str] = None
) -> str:
    """
    Intelligent Agent with MCP Tool Calling (Location/Amenities, EMI/Pricing Calculator, Calendar Bookings, Property Search).
    Executes autonomous tool calling with multi-provider fallbacks and tool execution interception.
    """
    litellm_tools = [
        {
            "type": "function",
            "function": {
                "name": "calc_home_loan_emi",
                "description": "Calculate monthly home loan EMI given loan amount in lakhs and optional interest rate and tenure.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "loan_amount_lakhs": {"type": "number", "description": "Loan amount in lakhs"},
                        "annual_interest_rate": {"type": "number", "description": "Interest rate percent (default 8.5)"},
                        "tenure_years": {"type": "integer", "description": "Loan tenure in years (default 20)"}
                    },
                    "required": ["loan_amount_lakhs"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "calc_property_breakdown",
                "description": "Calculate complete property price breakdown including Tamil Nadu stamp duty, registration charges, and on-road cost.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "base_price_lakhs": {"type": "number", "description": "Base property price in lakhs"},
                        "sqft": {"type": "number", "description": "Total built-up area in square feet"}
                    },
                    "required": ["base_price_lakhs"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "calculate_distance_and_route",
                "description": "Calculate real-world road distance, driving duration, and route directions between origin and destination in Chennai.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "origin": {"type": "string", "description": "Starting address or locality"},
                        "destination": {"type": "string", "description": "Destination address or property name"}
                    },
                    "required": ["origin", "destination"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "find_nearby_amenities",
                "description": "Find nearby amenities such as metro stations, hospitals, schools, IT parks, supermarkets around a location.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {"type": "string", "description": "Property locality or landmark"},
                        "amenity_type": {"type": "string", "description": "metro, hospital, school, it_park, supermarket, or restaurant"}
                    },
                    "required": ["location"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "calendar_check_slots",
                "description": "Check available site visit time slots for a specific real estate property on a requested date.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "property_name": {"type": "string", "description": "Name of the property"},
                        "preferred_date": {"type": "string", "description": "Requested date or day"}
                    },
                    "required": ["property_name"]
                }
            }
        }
    ]

    chat_messages: List[Dict[str, Any]] = [{"role": "system", "content": AGENT_SYSTEM_PROMPT}]
    if history:
        for msg in history[-6:]:
            r = msg.get("role") or msg.get("sender") or "user"
            c = msg.get("content") or msg.get("text") or ""
            if c.strip():
                chat_messages.append({"role": "assistant" if r in ["assistant", "ai", "bot"] else "user", "content": c})

    user_content = context_prompt if context_prompt else user_query
    chat_messages.append({"role": "user", "content": user_content})

    # Direct verified MCP Tool Context Auto-Enrichment (Route, Distance, EMI, Available Slots)
    mcp_data = await _resolve_direct_mcp_tool_context(user_query)
    enriched_prompt = f"{user_content}\n\n{mcp_data}" if mcp_data else user_content

    # Tier 1: Google Gemini 3.5 Flash / 3.5 Flash-Lite (Primary Engine - Ultra Fast & Intelligent)
    gemini_key = getattr(Setting, "GEMINI_API_KEY", "") or os.getenv("GEMINI_API_KEY", "")
    if gemini_key and gemini_key.strip():
        gemini_res = await generate_with_gemini(enriched_prompt, history=history)
        if gemini_res:
            return await _intercept_and_execute_raw_tool_calls(gemini_res, user_query=user_query)

    # Tier 2: Mistral AI (Tool Calling)
    mistral_key = getattr(Setting, "MISTRAL_API_KEY", "") or os.getenv("MISTRAL_API_KEY", "")
    if mistral_key and mistral_key.strip():
        try:
            import litellm
            from app.ai.mcp.mcp_server import execute_mcp_tool

            curr_messages = list(chat_messages)
            for _ in range(2):
                res = await asyncio.to_thread(
                    litellm.completion,
                    model="mistral/mistral-small-latest",
                    messages=curr_messages,
                    tools=litellm_tools,
                    api_key=mistral_key.strip(),
                    temperature=0.2,
                    timeout=10
                )

                if res and res.choices:
                    msg_obj = res.choices[0].message
                    tool_calls = getattr(msg_obj, "tool_calls", None) or []
                    if not tool_calls:
                        content_str = msg_obj.content
                        if content_str and len(content_str.strip()) > 15:
                            return await _intercept_and_execute_raw_tool_calls(content_str.strip(), user_query=user_query)
                        break

                    curr_messages.append(msg_obj)
                    for tc in tool_calls:
                        fn_name = tc.function.name
                        try:
                            fn_args = json.loads(tc.function.arguments) if isinstance(tc.function.arguments, str) else (tc.function.arguments or {})
                        except Exception:
                            fn_args = {}
                        tool_out = await execute_mcp_tool(fn_name, fn_args)

                        curr_messages.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "name": fn_name,
                            "content": json.dumps(tool_out, ensure_ascii=False) if not isinstance(tool_out, str) else tool_out
                        })

                    final_turn_res = await asyncio.to_thread(
                        litellm.completion,
                        model="mistral/mistral-small-latest",
                        messages=curr_messages,
                        api_key=mistral_key.strip(),
                        temperature=0.2,
                        timeout=10
                    )
                    if final_turn_res and final_turn_res.choices and final_turn_res.choices[0].message.content:
                        return await _intercept_and_execute_raw_tool_calls(final_turn_res.choices[0].message.content.strip(), user_query=user_query)

        except Exception as e:
            print(f"[Mistral Agent] Tool execution note: {e}")

    # Tier 3: DeepSeek AI Tool Calling Fallback
    deepseek_key = getattr(Setting, "DEEPSEEK_API_KEY", "") or os.getenv("DEEPSEEK_API_KEY", "")
    if deepseek_key and deepseek_key.strip():
        try:
            import litellm
            curr_messages = list(chat_messages)
            res = await asyncio.to_thread(
                litellm.completion,
                model="deepseek/deepseek-chat",
                messages=curr_messages,
                tools=litellm_tools,
                api_key=deepseek_key.strip(),
                temperature=0.2,
                timeout=10
            )
            if res and res.choices:
                msg_obj = res.choices[0].message
                tool_calls = getattr(msg_obj, "tool_calls", None) or []
                if not tool_calls and msg_obj.content and len(msg_obj.content.strip()) > 15:
                    return await _intercept_and_execute_raw_tool_calls(msg_obj.content.strip(), user_query=user_query)
        except Exception as e:
            print(f"[DeepSeek Agent] Tool execution note: {e}")

    # Tier 4: OpenRouter Fallback with active, fast free models
    openrouter_key = getattr(Setting, "OPENROUTER_API_KEY", "") or os.getenv("OPENROUTER_API_KEY", "")
    if openrouter_key and openrouter_key.strip():
        for or_model in [
            "openrouter/nvidia/nemotron-3.5-lightning:free",
            "openrouter/nex-agi/nex-n2.5-pro:free",
            "openrouter/nvidia/nemotron-3-super-120b-a12b:free",
            "openrouter/nex-agi/nex-n2.5-mini:free"
        ]:
            try:
                import litellm
                res = await asyncio.to_thread(
                    litellm.completion,
                    model=or_model,
                    messages=chat_messages,
                    api_key=openrouter_key.strip(),
                    temperature=0.2,
                    timeout=12
                )
                if res and res.choices and res.choices[0].message.content:
                    return await _intercept_and_execute_raw_tool_calls(res.choices[0].message.content.strip(), user_query=user_query)
            except Exception as e:
                print(f"[OpenRouter Agent {or_model}] note: {e}")

    fallback_res = await ask_llm(enriched_prompt, history=history)
    if fallback_res.startswith("Hello! I am your Real Estate AI Assistant") and mcp_data:
        return mcp_data
    return await _intercept_and_execute_raw_tool_calls(fallback_res, user_query=user_query)



async def ask_llm(prompt: str, history: Optional[List[Dict[str, Any]]] = None) -> str:
    """Direct fast LLM completion with multi-provider fallback (Gemini -> Mistral -> DeepSeek -> OpenRouter -> LiteLLM)."""
    # Tier 1: Gemini 3.5 Flash / 3.5 Flash-Lite (Highest accuracy, instantaneous)
    gemini_key = getattr(Setting, "GEMINI_API_KEY", "") or os.getenv("GEMINI_API_KEY", "")
    if gemini_key and gemini_key.strip():
        gemini_res = await generate_with_gemini(prompt, history=history)
        if gemini_res:
            return gemini_res

    messages_payload = [{"role": "system", "content": AGENT_SYSTEM_PROMPT}]
    if history:
        for msg in history[-6:]:
            role = msg.get("role") or msg.get("sender") or "user"
            content = msg.get("content") or msg.get("text") or ""
            if content.strip():
                mapped_role = "assistant" if role in ["assistant", "ai", "bot"] else "user"
                messages_payload.append({"role": mapped_role, "content": content})
    messages_payload.append({"role": "user", "content": prompt})

    # Tier 2: Mistral AI
    mistral_key = getattr(Setting, "MISTRAL_API_KEY", "") or os.getenv("MISTRAL_API_KEY", "")
    if mistral_key and mistral_key.strip():
        try:
            import litellm
            res = await asyncio.to_thread(
                litellm.completion,
                model="mistral/mistral-small-latest",
                messages=messages_payload,
                api_key=mistral_key.strip(),
                temperature=0.2,
                timeout=10
            )
            if res and res.choices and res.choices[0].message.content:
                return res.choices[0].message.content.strip()
        except Exception as e:
            print(f"[LLM Provider Mistral] Fallback note: {e}")

    # Tier 3: DeepSeek AI
    deepseek_key = getattr(Setting, "DEEPSEEK_API_KEY", "") or os.getenv("DEEPSEEK_API_KEY", "")
    if deepseek_key and deepseek_key.strip():
        try:
            import litellm
            res = await asyncio.to_thread(
                litellm.completion,
                model="deepseek/deepseek-chat",
                messages=messages_payload,
                api_key=deepseek_key.strip(),
                temperature=0.2,
                timeout=10
            )
            if res and res.choices and res.choices[0].message.content:
                return res.choices[0].message.content.strip()
        except Exception as e:
            print(f"[LLM Provider DeepSeek] Fallback note: {e}")

    # Tier 4: OpenRouter active free models
    openrouter_key = getattr(Setting, "OPENROUTER_API_KEY", "") or os.getenv("OPENROUTER_API_KEY", "")
    if openrouter_key and openrouter_key.strip():
        candidate_models = [
            "openrouter/nvidia/nemotron-3.5-lightning:free",
            "openrouter/nex-agi/nex-n2.5-pro:free",
            "openrouter/nvidia/nemotron-3-super-120b-a12b:free",
            "openrouter/nex-agi/nex-n2.5-mini:free"
        ]
        import litellm
        for current_model in candidate_models:
            try:
                res = await asyncio.to_thread(
                    litellm.completion,
                    model=current_model,
                    messages=messages_payload,
                    api_key=openrouter_key.strip(),
                    temperature=0.2,
                    timeout=12
                )
                if res and res.choices and res.choices[0].message.content:
                    return res.choices[0].message.content.strip()
            except Exception as e:
                print(f"[LLM Provider OpenRouter] Model {current_model} overload note: {e}. Trying next...")

    # Tier 5: Generic LiteLLM fallback
    for model_name in ["mistral/mistral-large-latest", "openai/gpt-4o-mini"]:
        try:
            import litellm
            res = await asyncio.to_thread(
                litellm.completion,
                model=model_name,
                messages=messages_payload,
                temperature=0.2,
                timeout=10
            )
            if res and res.choices and res.choices[0].message.content:
                return res.choices[0].message.content.strip()
        except Exception:
            pass

    # Tier 6: Direct Intelligent Fallback from Retrieved RAG Context
    # If LLMs are down, rate-limited, or unconfigured on remote host,
    # NEVER discard retrieved property listings! Return the formatted properties directly.
    if "<property_context>" in prompt:
        m = re.search(r'<property_context>(.*?)</property_context>', prompt, re.DOTALL)
        if m:
            ctx_text = m.group(1).strip()
            if ctx_text:
                return ctx_text

    if "No properties matching the user's requested criteria exist in our database" in prompt or "exact_match_found: False" in prompt:
        return "No properties found matching your requested criteria in our database. Please try searching with a different location, BHK, price range, or area preference."

    q_lower = prompt.lower().strip()
    if any(q_lower == g or q_lower.startswith(g + " ") for g in ["hi", "hello", "hey", "vanakkam", "namaste", "good morning", "good evening"]):
        return "Hello! I am your Real Estate AI Assistant. How can I help you find your dream property today?"

    return "Hello! I am your Real Estate AI Assistant. How can I help you find your dream property today?"
