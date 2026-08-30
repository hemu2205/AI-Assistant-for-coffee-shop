from typing import List, Dict, Any
from backend.services.db import get_all_products, get_product_by_id_or_name
from backend.services.recommendation import recommend_products as rec_engine
from backend.services.order_service import (
    get_order, add_to_order, update_order_item, remove_from_order, clear_order
)
from backend.rag.retriever import retriever

def tool_get_menu() -> List[Dict[str, Any]]:
    """Retrieve full coffee shop menu."""
    return get_all_products()

def tool_search_menu(query: str) -> List[Dict[str, Any]]:
    """Search menu by item name, category, or description."""
    products = get_all_products()
    q = query.lower()
    return [
        p for p in products 
        if q in p["name"].lower() or q in p["category"].lower() or q in p["description"].lower()
    ]

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

def tool_get_store_information() -> str:
    """Retrieve store location, hours, wifi, and policies."""
    return retriever.retrieve("store location hours wifi payment delivery customization")

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
