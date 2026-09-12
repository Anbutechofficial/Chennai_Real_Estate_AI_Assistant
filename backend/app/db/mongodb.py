import os
import certifi
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

from app.core.config import Setting

# Ensure environment variables are loaded
base_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(base_dir, "..", "..", ".env"))

_mongo_client = None


def get_mongo_client() -> AsyncIOMotorClient:
    global _mongo_client
    if _mongo_client is None:
        mongo_url = Setting.MONGODB_URL_KEY or os.getenv("MONGODB_URL_KEY")
        if not mongo_url:
            raise ValueError("MONGODB_URL_KEY is not set in environment or config.")
        _mongo_client = AsyncIOMotorClient(mongo_url, tlsCAFile=certifi.where(), serverSelectionTimeoutMS=5000)
    return _mongo_client


def get_db(db_name: str = "vector_demo_db"):
    client = get_mongo_client()
    return client[db_name]


def get_vector_collection(db_name: str = "vector_demo_db", collection_name: str = "documents"):
    return get_db(db_name)[collection_name]


def get_users_collection(db_name: str = "vector_demo_db"):
    """MongoDB collection for User authentication, verification, and hashed refresh tokens."""
    return get_db(db_name)["users"]


def get_profiles_collection(db_name: str = "vector_demo_db"):
    """MongoDB collection for User profile preferences, budget, and saved properties."""
    return get_db(db_name)["profiles"]


def get_site_visits_collection(db_name: str = "vector_demo_db"):
    """MongoDB collection for scheduled property site visits."""
    return get_db(db_name)["site_visits"]


async def init_db_indexes():
    """Initializes unique and lookup indexes on collections."""
    try:
        users_col = get_users_collection()
        await users_col.create_index("user_id", unique=True)
        await users_col.create_index("email", unique=True, sparse=True)

        profiles_col = get_profiles_collection()
        await profiles_col.create_index("user_id", unique=True)
        print("[MongoDB] User & Profile indexes initialized successfully.")
    except Exception as e:
        print(f"[MongoDB] Index creation note: {e}")
