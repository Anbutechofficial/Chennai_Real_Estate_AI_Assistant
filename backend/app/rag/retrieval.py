import os
import re
import time
import json
import asyncio
import numpy as np
import certifi
import pandas as pd
from dotenv import load_dotenv
from pymongo import MongoClient

from app.core.config import Setting
from app.rag.vector_store import VectorStore
from langchain_google_genai import GoogleGenerativeAIEmbeddings

# Load environment variables
base_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(base_dir, "..", "..", ".env"))

_vector_store = VectorStore()
_st_model = None
_gemini_client = None
_query_embedding_cache: dict[str, list[float]] = {}
_mongo_properties_cache: list[dict] = None
_local_properties_cache: list[dict] = None
_csv_cache: list[dict] = None
MAX_EMBEDDING_CACHE_SIZE = 1000


def clear_mongo_cache():
    global _mongo_properties_cache
    _mongo_properties_cache = None


async def load_mongo_properties() -> list[dict]:
    """
    Fetches property listings directly from MongoDB collection 'documents'.
    Falls back to local CSV if MongoDB is empty or unreachable.
    """
    global _mongo_properties_cache
    if _mongo_properties_cache is not None and len(_mongo_properties_cache) > 0:
        return _mongo_properties_cache

    try:
        from app.db.mongodb import get_vector_collection
        collection = get_vector_collection()
        cursor = collection.find({}, {"_id": 0, "text": 1, "metadata": 1})
        docs = await cursor.to_list(length=20000)

        if docs and len(docs) > 0:
            rows = []
            for doc in docs:
                text = doc.get("text", "")
                meta = doc.get("metadata") or {}
                p_name = str(meta.get("name", "")).strip()
                p_loc = str(meta.get("location", "")).strip()
                p_bhk = str(meta.get("bhk", "")).strip()

                area_val = meta.get("area_sqft", 0)
                try:
                    p_sqft = float(area_val) if area_val is not None else 0.0
                except (ValueError, TypeError):
                    p_sqft = 0.0

                price_val = meta.get("price_lakhs", 0)
                try:
                    p_price = float(price_val) if price_val is not None else 0.0
                except (ValueError, TypeError):
                    p_price = 0.0

                if not text:
                    text = f"{p_name} in {p_loc}: {p_bhk} BHK, {int(p_sqft) if p_sqft.is_integer() else p_sqft} sqft, Rs {p_price} Lakhs"

                rows.append({
                    "name": p_name,
                    "location": p_loc,
                    "bhk": p_bhk,
                    "area_sqft": p_sqft,
                    "price_lakhs": p_price,
                    "str": text
                })
            _mongo_properties_cache = rows
            print(f"[MongoDB] Successfully retrieved {len(_mongo_properties_cache)} documents from MongoDB Atlas.")
            return _mongo_properties_cache
    except Exception as e:
        print(f"MongoDB collection fetch note: {e}")

    return load_csv_properties()


def get_sentence_model():
    global _st_model
    if _st_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            try:
                _st_model = SentenceTransformer("all-MiniLM-L6-v2", local_files_only=True)
            except Exception:
                _st_model = SentenceTransformer("all-MiniLM-L6-v2")
        except Exception as e:
            print(f"SentenceTransformer initialization note: {e}")
            _st_model = False
    return _st_model if _st_model else None


def warmup_models():
    """Pre-warm sentence embedding model and property datasets into RAM at startup."""
    try:
        get_sentence_model()
        load_csv_properties()
        print("[Warmup] Completed: SentenceTransformer and property datasets loaded into RAM!")
    except Exception as e:
        print(f"Warmup warning: {e}")


def _sync_get_query_embedding(query: str) -> list[float]:
    global _gemini_client, _query_embedding_cache
    normalized_q = query.strip().lower()
    if normalized_q in _query_embedding_cache:
        return _query_embedding_cache[normalized_q]

    # Fast path 1: Local SentenceTransformer model (<15ms execution time)
    st_model = get_sentence_model()
    if st_model:
        try:
            emb = st_model.encode(query).tolist()
            if len(emb) < 768:
                emb = emb + [0.0] * (768 - len(emb))
            emb = emb[:768]
            if len(_query_embedding_cache) > MAX_EMBEDDING_CACHE_SIZE:
                _query_embedding_cache.clear()
            _query_embedding_cache[normalized_q] = emb
            return emb
        except Exception as e:
            print(f"SentenceTransformer embedding note: {e}")

    # Path 2: Gemini API embedding fallback
    gemini_key = Setting.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY")
    if gemini_key and gemini_key.strip():
        try:
            if _gemini_client is None:
                from google import genai
                _gemini_client = genai.Client(api_key=gemini_key.strip())
            from google.genai import types

            for model_id in ["gemini-embedding-001", "text-embedding-004"]:
                try:
                    res = _gemini_client.models.embed_content(
                        model=model_id,
                        contents=query,
                        config=types.EmbedContentConfig(output_dimensionality=768),
                    )
                    emb = []
                    if hasattr(res, "embeddings") and res.embeddings:
                        emb = list(res.embeddings[0].values)
                    elif hasattr(res, "embedding") and hasattr(res.embedding, "values"):
                        emb = list(res.embedding.values)

                    if emb:
                        if len(emb) < 768:
                            emb = emb + [0.0] * (768 - len(emb))
                        emb = emb[:768]
                        if len(_query_embedding_cache) > MAX_EMBEDDING_CACHE_SIZE:
                            _query_embedding_cache.clear()
                        _query_embedding_cache[normalized_q] = emb
                        return emb
                except Exception:
                    continue
        except Exception as e:
            print(f"Gemini query embedding note ({e}).")

    return []


async def get_query_embedding(query: str) -> list[float]:
    """Generate query embedding asynchronously with fast in-memory caching."""
    normalized_q = query.strip().lower()
    if normalized_q in _query_embedding_cache:
        return _query_embedding_cache[normalized_q]
    return await asyncio.to_thread(_sync_get_query_embedding, query)


def load_local_properties() -> list[dict]:
    global _local_properties_cache
    if _local_properties_cache is not None:
        return _local_properties_cache

    embeddings_file = os.path.abspath(os.path.join(base_dir, "..", "uploads", "embeddings.json"))
    if not os.path.exists(embeddings_file):
        embeddings_file = os.path.abspath(os.path.join(base_dir, "..", "..", "data", "embeddings.json"))

    if os.path.exists(embeddings_file):
        try:
            with open(embeddings_file, "r", encoding="utf-8") as file:
                _local_properties_cache = json.load(file)
                return _local_properties_cache
        except Exception:
            pass
    _local_properties_cache = []
    return _local_properties_cache


def load_csv_properties() -> list[dict]:
    global _csv_cache
    if _csv_cache is not None:
        return _csv_cache

    csv_file = os.path.abspath(os.path.join(base_dir, "..", "uploads", "Real_Estate_Assistant.csv"))
    if os.path.exists(csv_file):
        try:
            df = pd.read_csv(csv_file)
            rows = []
            for _, row in df.iterrows():
                p_name = str(row.get('name', '')).strip()
                p_loc = str(row.get('location', '')).strip()
                p_bhk = str(row.get('bhk', '')).strip()
                p_sqft = float(row.get('area_sqft', 0)) if pd.notnull(row.get('area_sqft')) else 0
                p_price = float(row.get('price_lakhs', 0)) if pd.notnull(row.get('price_lakhs')) else 0

                row_str = f"{p_name} in {p_loc}: {p_bhk} BHK, {int(p_sqft) if p_sqft.is_integer() else p_sqft} sqft, Rs {p_price} Lakhs"
                rows.append({
                    "name": p_name,
                    "location": p_loc,
                    "bhk": p_bhk,
                    "area_sqft": p_sqft,
                    "price_lakhs": p_price,
                    "str": row_str
                })
            _csv_cache = rows
            return _csv_cache
        except Exception as ex:
            print(f"CSV load exception: {ex}")
    _csv_cache = []
    return _csv_cache


def cosine_similarity(vec1, vec2):
    vec1 = np.array(vec1, dtype=float)
    vec2 = np.array(vec2, dtype=float)
    if vec1.shape != vec2.shape:
        return 0.0
    norm1, norm2 = np.linalg.norm(vec1), np.linalg.norm(vec2)
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return float(np.dot(vec1, vec2) / (norm1 * norm2))


async def retrieve(query: str, history: list = None, top_k: int = 5) -> list[dict]:
    """
    Smart multi-layer MongoDB property retrieval system:
    1. Conversational memory query resolution for follow-up questions.
    2. Primary data retrieval directly from MongoDB Atlas 'documents' collection.
    3. Atlas MongoDB Vector + Keyword Hybrid Search.
    4. Strict constraint filtering (BHK, location, price, area), intent-aware sorting, and failure handling.
    """
    effective_query = query
    if history:
        last_user_q = ""
        for item in reversed(history):
            role = item.get("role") or item.get("sender") or ""
            text = item.get("content") or item.get("text") or ""
            if role in ["user", "human", "You"] and text.strip() and text.strip() != query.strip():
                last_user_q = text.strip()
                break

        if last_user_q and any(w in query.lower() for w in [
            "which one", "what about", "cheapest", "largest", "another option",
            "first one", "recommend", "3 bhk", "2 bhk", "1 bhk", "its area", "its price",
            "like that", "instead", "from these", "difference"
        ]):
            curr_bhk = re.search(r'(\d+)\s*(?:bhk|bedroom)', query.lower())
            if curr_bhk:
                last_user_q_mod = re.sub(r'\d+\s*(?:bhk|bedroom)', f"{curr_bhk.group(1)} BHK", last_user_q, flags=re.IGNORECASE)
                effective_query = f"{last_user_q_mod} - {query}"
            else:
                effective_query = f"{last_user_q} - {query}"

    q_lower = effective_query.lower().strip()
    mongo_rows = await load_mongo_properties()

    # Calculate overall dataset statistics directly from MongoDB dataset
    total_count = len(mongo_rows)
    all_prices = [r["price_lakhs"] for r in mongo_rows if r["price_lakhs"] > 0]
    avg_price = round(sum(all_prices) / max(len(all_prices), 1), 1) if all_prices else 0.0

    # --- 1. Parameter & Intent Extraction ---
    # BHK matching
    bhk_match = re.search(r'(\d+)\s*(?:bhk|bedroom|bed)', q_lower)
    target_bhk = bhk_match.group(1) if bhk_match else None

    # Location matching
    known_locations = [
        "t nagar", "t. nagar", "tnagar", "nungambakkam", "mylapore", "alwarpet", "egmore",
        "royapettah", "adyar", "anna nagar", "kilpauk", "kodambakkam", "guindy", "velachery",
        "thiruvanmiyur", "besant nagar", "sholinganallur", "perungudi", "medavakkam",
        "pallikaranai", "perumbakkam", "omr", "ecr", "porur", "vadapalani", "ashok nagar",
        "saligramam", "virugambakkam", "valasaravakkam", "ambattur", "mogappair", "poonamallee",
        "avadi", "perambur", "madhavaram", "kolathur", "royapuram", "tondiarpet", "washermanpet",
        "manali", "ennore", "vyasarpadi", "puzhal", "tambaram", "east tambaram", "west tambaram",
        "chromepet", "pallavaram", "selaiyur", "vandalur", "guduvanchery", "guduvancheri",
        "perungalathur", "nanganallur", "madambakkam", "sithalapakkam", "villivakkam",
        "maduravoyal", "kovur", "urapakkam", "choolai", "mangadu", "kazhipattur", "thalambur",
        "mambakkam", "thirumazhisai", "madipakkam", "padur", "kelambakkam", "siruseri",
        "kotturpuram", "saidapet", "chetpet", "triplicane", "coimbatore", "bangalore"
    ]
    q_loc_check = q_lower.replace(".", "")
    found_locs = []
    for loc in known_locations:
        loc_clean = loc.replace(".", "")
        if loc_clean in q_loc_check or loc in q_lower:
            found_locs.append(loc_clean)
    found_locs = list(dict.fromkeys(found_locs))

    # If multiple locations exist, separate origin location (e.g. "at Porur", "from Guindy")
    # from the target property search location (e.g. "properties in Velachery")
    if len(found_locs) > 1:
        origin_match = re.search(r'(?:i am|currently|from)\s+(?:currently\s+)?(?:at|in|from)?\s*([a-zA-Z\s]+?)(?:[.,;]|\band\b|\bfind\b|\bsearch\b|\bshow\b|\bproperties\b|\bflats\b)', q_lower)
        if origin_match:
            cand_orig = origin_match.group(1).strip()
            filtered_locs = [l for l in found_locs if l not in cand_orig]
            if filtered_locs:
                found_locs = filtered_locs

    # Price constraint extraction
    min_price, max_price = None, None
    between_price = re.search(r'between\s*₹?\s*(\d+(?:\.\d+)?)\s*(?:and|to|-)\s*₹?\s*(\d+(?:\.\d+)?)', q_lower)
    if between_price:
        min_price = float(between_price.group(1))
        max_price = float(between_price.group(2))
    else:
        under_price = re.search(r'(?:under|below|less than|within|max|budget of)\s*₹?\s*(\d+(?:\.\d+)?)', q_lower)
        if under_price and 'sqft' not in q_lower[under_price.start():under_price.end()+12]:
            max_price = float(under_price.group(1))
        above_price = re.search(r'(?:above|more than|greater than|min)\s*₹?\s*(\d+(?:\.\d+)?)', q_lower)
        if above_price and 'sqft' not in q_lower[above_price.start():above_price.end()+12]:
            v = float(above_price.group(1))
            if v < 400: # Max individual price filter cap
                min_price = v
        around_price = re.search(r'around\s*₹?\s*(\d+(?:\.\d+)?)', q_lower)
        if around_price and 'sqft' not in q_lower[around_price.start():around_price.end()+12]:
            v = float(around_price.group(1))
            if v < 400:
                min_price = v * 0.75
                max_price = v * 1.25

    # Sqft constraint extraction
    min_sqft, max_sqft = None, None
    between_sqft = re.search(r'between\s*(\d+)\s*(?:and|to|-)\s*(\d+)\s*(?:sqft|sq\.ft|square feet)?', q_lower)
    if between_sqft:
        min_sqft = float(between_sqft.group(1))
        max_sqft = float(between_sqft.group(2))
    else:
        above_sqft = re.search(r'(?:above|more than|at least|greater than)\s*(\d+)\s*(?:sqft|sq\.ft|square feet)?', q_lower)
        if above_sqft:
            v = float(above_sqft.group(1))
            if v >= 100: # Sqft cap check
                min_sqft = v
        under_sqft = re.search(r'(?:below|under|less than)\s*(\d+)\s*(?:sqft|sq\.ft|square feet)', q_lower)
        if under_sqft:
            max_sqft = float(under_sqft.group(1))
        around_sqft = re.search(r'around\s*(\d+)\s*(?:sqft|sq\.ft|square feet)', q_lower)
        if around_sqft:
            v = float(around_sqft.group(1))
            min_sqft = v * 0.8
            max_sqft = v * 1.2

    # Intent-aware sorting
    sort_by = "relevance"
    if any(w in q_lower for w in ["cheapest", "lowest price", "least expensive", "minimum price", "affordable"]):
        sort_by = "price_asc"
    elif any(w in q_lower for w in ["most expensive", "costliest", "highest price", "maximum price", "luxury"]):
        sort_by = "price_desc"
    elif any(w in q_lower for w in ["largest", "biggest", "maximum area", "highest sqft", "spacious"]):
        sort_by = "sqft_desc"
    elif any(w in q_lower for w in ["best value", "value for money"]):
        sort_by = "value_per_sqft"

    # --- 2. Atlas VectorStore Primary Check (for generic unconstrained queries) ---
    query_embedding = await get_query_embedding(query)
    if query_embedding and not any([sort_by != "relevance", min_price, max_price, min_sqft, max_sqft, target_bhk, bool(found_locs)]):
        try:
            matches = await asyncio.wait_for(
                _vector_store.hybrid_search(
                    query_text=query,
                    query_embedding=query_embedding,
                    top_k=top_k
                ),
                timeout=1.0
            )
            if matches:
                return [{"score": m.get("score", 0.0), "text": m.get("text", "")} for m in matches]
        except (asyncio.TimeoutError, Exception):
            pass

    # --- 3. Strict Parameter Filtering ---
    exact_matches = []
    if mongo_rows:
        for r in mongo_rows:
            # BHK filter
            if target_bhk:
                row_bhk_match = re.search(r'\d+', str(r["bhk"]))
                row_bhk_num = row_bhk_match.group(0) if row_bhk_match else str(r["bhk"]).strip()
                if row_bhk_num != str(target_bhk).strip():
                    continue

            # Location filter
            if found_locs:
                loc_hit = any(fl in r["location"].lower() or fl in r["name"].lower() for fl in found_locs)
                if not loc_hit:
                    continue

            # Price filters
            if min_price is not None and r["price_lakhs"] < min_price:
                continue
            if max_price is not None and r["price_lakhs"] > max_price:
                continue

            # Sqft filters
            if min_sqft is not None and r["area_sqft"] < min_sqft:
                continue
            if max_sqft is not None and r["area_sqft"] > max_sqft:
                continue

            exact_matches.append(r)

    # --- 4. Sorting & Formatting Results ---
    exact_match_found = True
    match_count = len(exact_matches)

    if not exact_matches:
        # RETRIEVAL FAILURE / NO MATCH CASE - No fallback property listings
        exact_match_found = False
        results = []
    else:
        # Apply sort order to exact matches
        if sort_by == "price_asc":
            exact_matches.sort(key=lambda x: x["price_lakhs"])
        elif sort_by == "price_desc":
            exact_matches.sort(key=lambda x: x["price_lakhs"], reverse=True)
        elif sort_by == "sqft_desc":
            exact_matches.sort(key=lambda x: x["area_sqft"], reverse=True)
        elif sort_by == "value_per_sqft":
            exact_matches.sort(key=lambda x: (x["price_lakhs"] * 100000) / max(x["area_sqft"], 1))

        results = exact_matches[:top_k]

    # Format document list with metadata headers
    final_docs = []
    meta_header = (
        f"[METADATA] exact_match_found: {exact_match_found} | "
        f"matching_count: {match_count} | "
        f"total_database_listings: {total_count} | "
        f"average_price: Rs {avg_price} Lakhs"
    )
    final_docs.append({"score": 1.0, "text": meta_header})

    for doc in results:
        final_docs.append({"score": 1.0, "text": doc["str"]})

    return final_docs



