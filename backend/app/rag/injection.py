import os
import asyncio
import pandas as pd
from dotenv import load_dotenv

from langchain_core.documents import Document
from langchain_google_genai import GoogleGenerativeAIEmbeddings

from app.core.config import Setting
from app.rag.vector_store import VectorStore

# Load .env searching parent directories
base_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(base_dir, "..", "..", ".env"))

GEMINI_API_KEY = Setting.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY")


async def ingest_csv(file_path: str, batch_size: int = 50):
    if not os.path.exists(file_path):
        print(f"Error: {file_path} not found.")
        return

    # 1. Read CSV
    df = pd.read_csv(file_path)
    print(f"Loaded {len(df)} rows from {file_path}")

    vector_store = VectorStore()

    # Initialize LangChain Google embeddings if key present
    lc_embeddings = None
    if GEMINI_API_KEY:
        try:
            lc_embeddings = GoogleGenerativeAIEmbeddings(
                model="models/gemini-embedding-001",
                google_api_key=GEMINI_API_KEY.strip()
            )
        except Exception as e:
            print(f"LangChain GoogleGenerativeAIEmbeddings init note: {e}")

    # 2. Process in batches
    for i in range(0, len(df), batch_size):
        batch = df.iloc[i : i + batch_size]

        ids = [str(idx) for idx in batch.index]
        documents = [
            f"{row.get('name', '')} in {row.get('location', '')}: {row.get('bhk', '')} BHK, {row.get('area_sqft', '')} sqft, Rs {row.get('price_lakhs', '')} Lakhs"
            for _, row in batch.iterrows()
        ]
        metadatas = [row.to_dict() for _, row in batch.iterrows()]

        # Convert to LangChain Document objects
        langchain_docs = [
            Document(page_content=text, metadata=meta)
            for text, meta in zip(documents, metadatas)
        ]

        embeddings = []
        if lc_embeddings:
            for attempt in range(3):
                try:
                    embeddings = await lc_embeddings.aembed_documents(documents)
                    break
                except Exception as e:
                    if ("429" in str(e) or "RESOURCE_EXHAUSTED" in str(e)) and attempt < 2:
                        await asyncio.sleep(5 * (attempt + 1))
                    else:
                        print(f"LangChain embedding attempt failed: {e}. Falling back to SentenceTransformer.")
                        break

        if not embeddings:
            from sentence_transformers import SentenceTransformer
            st_model = SentenceTransformer("all-MiniLM-L6-v2")
            raw_embeddings = st_model.encode(documents).tolist()
            # Pad 384-dim embeddings to 768-dims for MongoDB index uniformity
            embeddings = [emb + [0.0] * (768 - len(emb)) for emb in raw_embeddings]

        await vector_store.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas
        )

        print(f"Ingested rows {i} to {i + len(batch)} into MongoDB Atlas VectorStore.")
        await asyncio.sleep(1)

    try:
        from app.rag.retrieval import clear_mongo_cache
        clear_mongo_cache()
    except Exception:
        pass


if __name__ == "__main__":
    csv_file = os.path.abspath(os.path.join(base_dir, "..", "uploads", "Real_Estate_Assistant.csv"))
    asyncio.run(ingest_csv(csv_file))
