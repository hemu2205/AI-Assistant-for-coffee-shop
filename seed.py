import os
import json
import re
from pathlib import Path
try:
    from backend.rag.pinecone_client import (
        ensure_index_exists,
        get_embedding,
        INDEX_NAME,
        EMBEDDING_DIMENSION,
        METRIC
    )
except ImportError:
    from pinecone_client import (
        ensure_index_exists,
        get_embedding,
        INDEX_NAME,
        EMBEDDING_DIMENSION,
        METRIC
    )

def slugify(text: str) -> str:
    """Slugify text for vector IDs: e.g. 'Caffè Latte' -> 'caffe-latte'."""
    text = text.lower()
    # Normalize accented characters
    text = re.sub(r'[àáâãäå]', 'a', text)
    text = re.sub(r'[èéêë]', 'e', text)
    text = re.sub(r'[ìíîï]', 'i', text)
    text = re.sub(r'[òóôõö]', 'o', text)
    text = re.sub(r'[ùúûü]', 'u', text)
    text = re.sub(r'[^a-z0-9]+', '-', text).strip('-')
    return text

def seed_menu(menu_path: str = None):
    """Seed Pinecone index with embeddings and metadata from menu.json."""
    if menu_path is None:
        menu_path = Path(__file__).parent / "data" / "menu.json"
    else:
        menu_path = Path(menu_path)

    if not menu_path.exists():
        raise FileNotFoundError(f"Menu file not found at {menu_path}")

    with open(menu_path, "r", encoding="utf-8") as f:
        menu_items = json.load(f)

    print(f"Loaded {len(menu_items)} items from {menu_path}")

    # 1. Ensure Index exists (dim=768, metric=cosine)
    index = ensure_index_exists()

    # 2. Prepare vector batch
    vectors_to_upsert = []
    current_ids = set()

    for item in menu_items:
        item_id = slugify(item["name"])
        current_ids.add(item_id)

        # Embedding text: name + description
        text_to_embed = f"{item['name']}: {item['description']}"
        embedding = get_embedding(text_to_embed)

        metadata = {
            "id": item.get("id", ""),
            "name": item.get("name", ""),
            "category": item.get("category", ""),
            "description": item.get("description", ""),
            "price": float(item.get("price", 0.0)),
            "image_url": item.get("image_url", ""),
            "ingredients": item.get("ingredients", []),
            "caffeine": item.get("caffeine", ""),
            "sweetness": item.get("sweetness", ""),
            "temperature": item.get("temperature", ""),
            "milk_options": item.get("milk_options", []),
            "dietary_tags": item.get("dietary_tags", []),
            "tags": item.get("dietary_tags", []),  # alias for prompt requirement
            "allergens": item.get("allergens", []),
            "calories": int(item.get("calories", 0))
        }

        vectors_to_upsert.append({
            "id": item_id,
            "values": embedding,
            "metadata": metadata
        })

    # 3. Clean up deleted items if any
    try:
        existing_id_pages = index.list(prefix="")
        existing_ids = set()
        for page in existing_id_pages:
            existing_ids.update(page)
        
        stale_ids = list(existing_ids - current_ids)
        if stale_ids:
            print(f"Removing {len(stale_ids)} stale vector(s): {stale_ids}")
            index.delete(ids=stale_ids)
    except Exception as e:
        # Some serverless index configs don't support list() immediately if empty
        pass

    # 4. Batched Upsert (all items in one single call)
    index.upsert(vectors=vectors_to_upsert)

    try:
        try:
            from backend.rag.pinecone_client import invalidate_vector_cache, warm_vector_cache
        except ImportError:
            from pinecone_client import invalidate_vector_cache, warm_vector_cache
        invalidate_vector_cache()
        warm_vector_cache()
    except Exception:
        pass

    print(f"Successfully seeded {len(vectors_to_upsert)} menu items into Pinecone index '{INDEX_NAME}'!")
    return len(vectors_to_upsert)

if __name__ == "__main__":
    seed_menu()
