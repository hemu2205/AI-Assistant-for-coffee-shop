import os
import time
import math
from functools import lru_cache
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from pinecone import Pinecone, ServerlessSpec
from google import genai
from google.genai import types

load_dotenv()

INDEX_NAME = "coffee-menu"
EMBEDDING_DIMENSION = 768
METRIC = "cosine"
EMBEDDING_MODEL = "gemini-embedding-001"

_pc_instance: Optional[Pinecone] = None
_genai_client: Optional[genai.Client] = None
_index_instance = None
_vector_cache: List[Dict[str, Any]] = []

def get_pinecone_client() -> Pinecone:
    """Initialize and return the Pinecone client singleton."""
    global _pc_instance
    if _pc_instance is None:
        api_key = os.getenv("PINECONE_API_KEY")
        if not api_key:
            raise ValueError("PINECONE_API_KEY environment variable is not set. Please set it in .env.")
        _pc_instance = Pinecone(api_key=api_key)
    return _pc_instance

def get_genai_client() -> genai.Client:
    """Initialize and return the Google GenAI client singleton."""
    global _genai_client
    if _genai_client is None:
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is not set. Please set it in .env.")
        _genai_client = genai.Client(api_key=api_key)
    return _genai_client

@lru_cache(maxsize=1024)
def _cached_embedding(text: str) -> tuple:
    """Internal LRU-cached embedding generation."""
    client = get_genai_client()
    response = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=text,
        config=types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIMENSION)
    )
    return tuple(response.embeddings[0].values)

def get_embedding(text: str) -> list[float]:
    """Generate a 768-dimensional embedding with query normalization and LRU caching."""
    normalized = " ".join(text.strip().lower().split())
    if not normalized:
        normalized = "coffee"
    return list(_cached_embedding(normalized))

def ensure_index_exists(cloud: str = "aws", region: str = "us-east-1"):
    """Ensure the coffee-menu index exists with dimension=768, metric=cosine. Create if missing."""
    global _index_instance
    pc = get_pinecone_client()
    existing_indexes = pc.list_indexes().names()
    if INDEX_NAME not in existing_indexes:
        print(f"Creating Pinecone index '{INDEX_NAME}' (dimension={EMBEDDING_DIMENSION}, metric={METRIC})...")
        pc.create_index(
            name=INDEX_NAME,
            dimension=EMBEDDING_DIMENSION,
            metric=METRIC,
            spec=ServerlessSpec(cloud=cloud, region=region)
        )
        while not pc.describe_index(INDEX_NAME).status['ready']:
            time.sleep(1)
        print(f"Index '{INDEX_NAME}' is now ready!")
    _index_instance = pc.Index(INDEX_NAME)
    return _index_instance

def get_menu_index():
    """Get the persistent Pinecone index handle to reuse connection pools."""
    global _index_instance
    if _index_instance is None:
        pc = get_pinecone_client()
        _index_instance = pc.Index(INDEX_NAME)
    return _index_instance

def warm_vector_cache() -> List[Dict[str, Any]]:
    """Fetch vectors and metadata from Pinecone into memory for <1ms semantic vector search."""
    global _vector_cache
    if not _vector_cache:
        try:
            index = get_menu_index()
            id_pages = index.list(prefix="")
            all_ids = []
            for page in id_pages:
                for item in page:
                    item_id = item.id if hasattr(item, "id") else str(item)
                    all_ids.append(item_id)
            if all_ids:
                fetched = index.fetch(ids=all_ids)
                records = []
                for v in fetched.vectors.values():
                    norm = math.sqrt(sum(x * x for x in v.values))
                    records.append({
                        "id": v.id,
                        "values": v.values,
                        "norm": norm if norm > 0 else 1.0,
                        "metadata": v.metadata
                    })
                _vector_cache = records
        except Exception:
            pass
    return _vector_cache

def invalidate_vector_cache():
    """Clear in-memory vector cache (e.g. after re-seeding menu)."""
    global _vector_cache
    _vector_cache = []

def query_menu_vectors(query_vector: list[float], top_k: int = 4) -> List[Dict[str, Any]]:
    """
    Perform sub-millisecond vector similarity search against cached Pinecone records.
    Falls back to direct Pinecone API query if cache is unavailable.
    """
    records = warm_vector_cache()
    if records:
        norm_q = math.sqrt(sum(x * x for x in query_vector))
        if norm_q == 0:
            norm_q = 1.0
        
        scored = []
        for r in records:
            dot = sum(a * b for a, b in zip(query_vector, r["values"]))
            cosine = dot / (norm_q * r["norm"])
            scored.append({
                "id": r["id"],
                "score": cosine,
                "metadata": r["metadata"]
            })
        
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]
    
    # Direct Pinecone network query fallback
    index = get_menu_index()
    res = index.query(vector=query_vector, top_k=top_k, include_metadata=True)
    return [
        {
            "id": m.id,
            "score": m.score,
            "metadata": m.metadata
        }
        for m in res.matches
    ]
