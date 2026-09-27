import os
import json
from typing import List, Dict, Any
from backend.services.db import get_all_products, get_product_by_id_or_name
from backend.services.recommendation import recommend_products as rec_engine
from backend.services.order_service import (
    get_order, add_to_order, update_order_item, remove_from_order, clear_order
)
from backend.rag.retriever import retriever

# Sane default similarity threshold (easily tunable via env var)
SIMILARITY_SCORE_THRESHOLD = float(os.getenv("SIMILARITY_SCORE_THRESHOLD", "0.50"))

def get_menu(query: str = "") -> str:
    """
    Search and retrieve relevant coffee shop menu items using Pinecone vector semantic search.
    
    Args:
        query: Natural language query describing desired beverages, food, or customer taste preferences.
        
    Returns:
        JSON string containing matching menu items with details (name, description, price, tags, allergens, etc.)
        or an explicit note if no relevant items meet the similarity threshold.
    """
    try:
        try:
            from backend.rag.pinecone_client import query_menu_vectors, get_embedding
        except ImportError:
            from pinecone_client import query_menu_vectors, get_embedding
        
        search_query = query.strip() if (query and query.strip()) else "popular coffee and bakery items"
        query_vector = get_embedding(search_query)
        matches = query_menu_vectors(query_vector, top_k=4)
        filtered_items = []
        for match in matches:
            score = match.get("score", 0.0)
            if score >= SIMILARITY_SCORE_THRESHOLD:
                meta = match.get("metadata", {})
                filtered_items.append({
                    "name": meta.get("name"),
                    "category": meta.get("category"),
                    "description": meta.get("description"),
                    "price": meta.get("price"),
                    "tags": meta.get("tags", meta.get("dietary_tags", [])),
                    "allergens": meta.get("allergens", []),
                    "caffeine": meta.get("caffeine"),
                    "temperature": meta.get("temperature"),
                    "calories": meta.get("calories"),
                    "similarity_score": round(score, 4)
                })
        
        if not filtered_items:
            return json.dumps({
                "items": [],
                "note": "no relevant menu items found"
            }, indent=2)
            
        return json.dumps({
            "items": filtered_items
        }, indent=2)

    except ValueError as e:
        return json.dumps({
            "items": [],
            "error": f"Configuration error: {str(e)}",
            "status": "auth_or_config_error"
        })
    except Exception as e:
        err_msg = str(e)
        if "NotFound" in err_msg or "404" in err_msg or "not found" in err_msg.lower():
            status = "index_missing"
            detail = "Pinecone index 'coffee-menu' not found. Please run seed.py."
        elif "Unauthorized" in err_msg or "401" in err_msg or "forbidden" in err_msg.lower():
            status = "auth_error"
            detail = "Pinecone authentication failed. Please verify PINECONE_API_KEY in .env."
        else:
            status = "connection_error"
            detail = f"Pinecone vector retrieval failed: {err_msg}"
            
        return json.dumps({
            "items": [],
            "error": detail,
            "status": status
        })

def tool_get_menu(query: str = "") -> str:
    """Retrieve relevant coffee shop menu items using vector search."""
    return get_menu(query)

def tool_search_menu(query: str) -> str:
    """Search menu items using vector similarity search."""
    return get_menu(query)

def tool_get_product_details(product_name: str) -> Dict[str, Any]:
    """Get detailed specification of a specific product."""
    p = get_product_by_id_or_name(product_name)
    if not p:
        return {"error": f"Product '{product_name}' not found."}
    return p

def tool_recommend_products(temperature: str = None, sweetness: str = None, caffeine: str = None, diet: str = None, budget: float = 500) -> List[Dict[str, Any]]:
    """Recommend products based on user preferences."""
    prefs = {
        "temperature": temperature,
        "sweetness": sweetness,
        "caffeine": caffeine,
        "diet": diet,
        "budget": budget
    }
    return rec_engine(prefs)

def tool_check_allergens(product_name: str) -> Dict[str, Any]:
    """Check allergen information for a product."""
    p = get_product_by_id_or_name(product_name)
    if not p:
        return {"error": f"Product '{product_name}' not found."}
    return {
        "product_name": p["name"],
        "allergens": p["allergens"],
        "dietary_tags": p["dietary_tags"]
    }

def tool_get_store_information(query: str = "") -> str:
    """Retrieve store location, hours, wifi, refund policy, byo cup discount, pets, or allergens."""
    search_query = query.strip() if query and query.strip() else "store location hours wifi refund byo cup pets allergens"
    return retriever.retrieve(search_query)

def tool_create_order(session_id: str, product_name: str, quantity: int = 1) -> Dict[str, Any]:
    """Add product to current order."""
    return add_to_order(session_id=session_id, product_name=product_name, quantity=quantity)

def tool_get_current_order(session_id: str) -> Dict[str, Any]:
    """Get user's current order summary."""
    return get_order(session_id)

def tool_update_order(session_id: str, product_name: str, quantity: int) -> Dict[str, Any]:
    """Update item quantity in current order."""
    return update_order_item(session_id=session_id, product_name=product_name, quantity=quantity)

def tool_remove_from_order(session_id: str, product_name: str) -> Dict[str, Any]:
    """Remove item completely from order."""
    return remove_from_order(session_id=session_id, product_name=product_name)

def tool_clear_order(session_id: str) -> Dict[str, Any]:
    """Clear all items from current order."""
    return clear_order(session_id)
