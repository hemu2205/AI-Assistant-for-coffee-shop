import os
import json
import re
from typing import Dict, Any, List
from google.adk import Agent
from google import genai
from google.genai import types

from backend.rag.retriever import retriever
from backend.services.recommendation import recommend_products
from backend.services.order_service import (
    add_to_order, get_order, remove_from_order, clear_order
)
from backend.services.db import (
    get_all_products, get_product_by_id_or_name,
    save_chat_message, get_chat_history, clear_chat_history
)
from backend.agent.tools import (
    tool_get_menu, tool_search_menu, tool_get_product_details,
    tool_recommend_products, tool_check_allergens, tool_get_store_information
)

SYSTEM_INSTRUCTION = """
You are BrewBuddy, an expert customer-facing coffee shop AI assistant developed with the Google Agent Development Kit (ADK).
Help customers choose beverages & food based on preferences, answer menu & store policy questions using the provided knowledge base tools, and manage customer orders.
Format all responses clearly using Markdown with bullet points, bold key terms, and clean section breaks.
When a user asks about a specific product (e.g., Chocolate Muffin or Iced Latte), provide its full details including price, description, ingredients, allergens, calories, and caffeine.
When a user asks for recommendations, popular drinks, or the 'best coffee', present top signature beverages with prices and descriptions.
When a user adds or modifies items in their order, confirm the added items and provide the updated order subtotal and total.
Never invent menu items, prices, ingredients, or allergen information. If information is unavailable, clearly tell the customer.
"""

# Initialize Official Google ADK Agent Instance
brewbuddy_adk_agent = Agent(
    name="BrewBuddy_ADK_Agent",
    model="gemini-2.5-flash",
    description="Customer-facing Coffee Shop Assistant Agent built with Google ADK",
    instruction=SYSTEM_INSTRUCTION,
    tools=[
        tool_get_menu,
        tool_search_menu,
        tool_get_product_details,
        tool_recommend_products,
        tool_check_allergens,
        tool_get_store_information
    ]
)


def format_rag_fallback_response(raw_context: str) -> str:
    """Format raw RAG text into clean, Gemini-style markdown with bullet points and bold headers."""
    if not raw_context.strip():
        return "I'm BrewBuddy! I can recommend coffee based on your preferences, check ingredients, or place your order. How can I help you today?"
    
    sections = raw_context.split("---")
    formatted_chunks = []
    
    for sec in sections:
        sec_clean = sec.strip()
        if not sec_clean:
            continue
        
        sec_clean = re.sub(r'Q:\s*(.*?)\n\s*A:\s*(.*)', r'* **\1**\n  \2', sec_clean, flags=re.DOTALL)
        lines = sec_clean.split("\n")
        processed_lines = []
        for line in lines:
            line_str = line.strip()
            if not line_str:
                continue
            if line_str.startswith("-"):
                processed_lines.append(f"* **{line_str[1:].strip()}**" if ":" in line_str else f"* {line_str[1:].strip()}")
            elif line_str.isupper() or line_str.endswith(":"):
                processed_lines.append(f"\n### {line_str}")
            else:
                processed_lines.append(line_str)
        
        formatted_chunks.append("\n".join(processed_lines))

    return "Here is what I found for you:\n\n" + "\n\n".join(formatted_chunks)

def format_product_detail_response(p: Dict[str, Any]) -> str:
    """Format exact product details into clean markdown."""
    allergens_str = ", ".join(p["allergens"]) if p["allergens"] else "None (Allergen-free)"
    ingredients_str = ", ".join(p["ingredients"]) if p["ingredients"] else "Standard"
    dietary_str = ", ".join(p["dietary_tags"]) if p["dietary_tags"] else "Standard"

    return f"""### ☕ **{p['name']}** (₹{p['price']})
{p['description']}

* **Category:** {p['category']}
* **Calories:** {p['calories']} kcal | **Caffeine Level:** {p['caffeine'].capitalize()}
* **Ingredients:** {ingredients_str}
* **Allergens:** {allergens_str}
* **Dietary Tags:** {dietary_str}

Would you like me to add a **{p['name']}** to your order?"""

def format_recommendations_response(products: List[Dict[str, Any]]) -> str:
    """Format top product recommendations into clean markdown."""
    items_md = []
    for p in products[:3]:
        items_md.append(f"* ☕ **{p['name']}** (₹{p['price']}) — {p['description']} (*{p['caffeine'].capitalize()} caffeine, {p['calories']} kcal*)")
    
    return "Here are our **best signature coffee & beverage recommendations**:\n\n" + "\n".join(items_md) + "\n\nWhich one would you like to view details or add to your order?"


def process_chat_message(message: str, session_id: str, preferences: Dict[str, Any] = None) -> Dict[str, Any]:
    api_key = os.getenv("GOOGLE_API_KEY")
    
    # Save incoming user message to persistent DB
    save_chat_message(session_id, "user", message)
    
    # Load past conversation context
    history_records = get_chat_history(session_id, limit=6)
    history_context = "\n".join([f"{h['role'].capitalize()}: {h['message']}" for h in history_records[:-1]])
    
    recommended_products = []
    msg_lower = message.lower()
    tool_called = None
    action_qty = 1

    # Check for direct product inquiry
    matched_product = None
    all_prods = get_all_products()
    for p in all_prods:
        if p["name"].lower() in msg_lower:
            matched_product = p
            break

    # Handle direct cart actions
    is_cart_action = False
    if any(k in msg_lower for k in ["add", "order", "get me", "want a", "buy", "cart"]):
        if any(verb in msg_lower for verb in ["add", "order", "get", "want", "buy", "put"]):
            is_cart_action = True
            tool_called = "add_to_order"
            if matched_product:
                for word in msg_lower.split():
                    if word.isdigit():
                        action_qty = int(word)
                add_to_order(session_id, matched_product["name"], quantity=action_qty)

    elif "remove" in msg_lower or "delete" in msg_lower:
        is_cart_action = True
        tool_called = "remove_from_order"
        if matched_product:
            remove_from_order(session_id, matched_product["name"])

    elif "clear" in msg_lower and "order" in msg_lower:
        is_cart_action = True
        tool_called = "clear_order"
        clear_order(session_id)

    # Expanded recommendation terms (best coffee, top drinks, recommendations, etc.)
    rec_terms = ["recommend", "suggest", "best", "top", "popular", "good", "favorite", "favourite", "something", "cold", "hot", "sweet", "caffeine", "milk", "diet", "vegan"]
    is_rec_query = any(k in msg_lower for k in rec_terms) and not matched_product and not is_cart_action

    if is_rec_query:
        tool_called = tool_called or "recommend_products"
        user_prefs = preferences or {}
        if "cold" in msg_lower: user_prefs["temperature"] = "cold"
        if "hot" in msg_lower: user_prefs["temperature"] = "hot"
        if "low sweet" in msg_lower or "not too sweet" in msg_lower: user_prefs["sweetness"] = "low"
        if "high caffeine" in msg_lower or "strong" in msg_lower: user_prefs["caffeine"] = "high"
        if "medium caffeine" in msg_lower: user_prefs["caffeine"] = "medium"
        if "low caffeine" in msg_lower: user_prefs["caffeine"] = "low"
        if "dairy-free" in msg_lower or "dairy free" in msg_lower or "vegan" in msg_lower:
            user_prefs["diet"] = "vegan"
            
        recommended_products = recommend_products(user_prefs)

    # Do NOT run RAG retrieval on cart actions or recommendation queries
    rag_context = "" if (is_rec_query or is_cart_action or matched_product) else retriever.retrieve(message)

    # Official Google ADK Agent Execution Loop
    if api_key:
        try:
            client = genai.Client(api_key=api_key)
            prompt = f"{brewbuddy_adk_agent.instruction}\n\nRecent History:\n{history_context}\n\nRetrieved Context:\n{rag_context}\n\nCustomer Query: {message}"
            
            config = types.GenerateContentConfig(
                system_instruction=brewbuddy_adk_agent.instruction,
                tools=brewbuddy_adk_agent.tools,
                temperature=0.3
            )
            
            response = client.models.generate_content(
                model=brewbuddy_adk_agent.model,
                contents=prompt,
                config=config
            )
            
            reply = response.text
            save_chat_message(session_id, "assistant", reply)
            current_order = get_order(session_id)
            recs = [matched_product] if matched_product else recommended_products
            return {
                "response": reply,
                "recommended_products": recs,
                "order": current_order,
                "tool_called": tool_called
            }
        except Exception:
            pass

    current_order = get_order(session_id)
    
    if is_cart_action and matched_product:
        item_total = matched_product['price'] * action_qty
        reply = f"✅ Added **{action_qty}x {matched_product['name']}** (₹{item_total:.0f}) to your order!\n\n* **Current Subtotal:** ₹{current_order['subtotal']:.2f}\n* **GST (5%):** ₹{current_order['tax']:.2f}\n* **Order Total:** ₹{current_order['total']:.2f}\n\nWould you like to add anything else or place your order?"
        recommended_products = [matched_product]
    elif is_cart_action and "clear" in msg_lower:
        reply = "🗑️ Your order has been cleared!"
    elif matched_product and not is_cart_action:
        reply = format_product_detail_response(matched_product)
        recommended_products = [matched_product]
    elif recommended_products:
        reply = format_recommendations_response(recommended_products)
    elif rag_context:
        reply = format_rag_fallback_response(rag_context)
    elif "total" in msg_lower or "order" in msg_lower:
        reply = f"Your current order total is **₹{current_order['total']:.2f}**\n\n* **Subtotal:** ₹{current_order['subtotal']:.2f}\n* **GST (5%):** ₹{current_order['tax']:.2f}"
    else:
        reply = "I'm **BrewBuddy**! I can recommend beverages based on your taste, caffeine, and dietary preferences, check ingredients & allergens, or take your order. How can I help you today?"

    save_chat_message(session_id, "assistant", reply)

    return {
        "response": reply,
        "recommended_products": recommended_products,
        "order": current_order,
        "tool_called": tool_called
    }
