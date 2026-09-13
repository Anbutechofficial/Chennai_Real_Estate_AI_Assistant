import os
import asyncio
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from app.routes.assistant import router as assistant_router
from app.routes.auth import router as auth_router
from app.routes.map import router as map_router
from app.routes.mcp_route import router as mcp_router
from app.rag.injection import ingest_csv
from app.rag.retrieval import warmup_models
from app.db.mongodb import get_vector_collection, init_db_indexes

app = FastAPI(title="Real Estate AI Assistant")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "https://real-estate-rag-backend.onrender.com",
    ],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$|^https://.*\.pages\.dev$|^https://.*\.onrender\.com$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(assistant_router)
app.include_router(auth_router)
app.include_router(map_router)
app.include_router(mcp_router)


@app.on_event("startup")
async def startup_db_check():
    """Auto-ingest property CSV into MongoDB Atlas if collection is empty, initialize indexes, and warm up models."""
    asyncio.create_task(init_db_indexes())
    asyncio.create_task(asyncio.to_thread(warmup_models))
    try:
        collection = get_vector_collection()
        count = await collection.count_documents({})
        if count == 0:
            print("MongoDB collection 'documents' is empty. Triggering background ingestion...")
            base_dir = os.path.dirname(os.path.abspath(__file__))
            csv_file = os.path.abspath(os.path.join(base_dir, "uploads", "Real_Estate_Assistant.csv"))
            asyncio.create_task(ingest_csv(csv_file))
        else:
            print(f"MongoDB collection 'documents' already contains {count} chunks/documents.")
    except Exception as e:
        print(f"Startup MongoDB check note: {e}")



@app.get("/")
def landing_page():
    return {
        "message": "Real Estate AI Assistant is Running!"
    }


@app.get("/health")
def health():
    return {
        "status": "BACKEND IS HEALTHY"
    }


@app.post("/ingest")
async def trigger_ingestion(background_tasks: BackgroundTasks):
    """Manual endpoint to trigger dataset ingestion into MongoDB Atlas."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    csv_file = os.path.abspath(os.path.join(base_dir, "uploads", "Real_Estate_Assistant.csv"))
    background_tasks.add_task(ingest_csv, csv_file)
    return {"message": "CSV ingestion started in background!"}
