import os
import json
import re
from typing import Dict, Any, List, Optional
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
    get_menu, tool_get_menu, tool_search_menu, tool_get_product_details,
    tool_recommend_products, tool_check_allergens, tool_get_store_information,
    tool_create_order, tool_get_current_order, tool_update_order,
    tool_remove_from_order, tool_clear_order
)

SYSTEM_INSTRUCTION = """
You are BrewBuddy, an expert customer-facing coffee shop AI assistant developed with the Google Agent Development Kit (ADK).
Your purpose is to help customers choose beverages and bakery snacks using Pinecone vector search over our official menu, answer store policy and FAQ questions, and manage orders.

STRICT GROUNDING & RETRIEVAL RULES:
1. Grounding in get_menu():
   - When asked about coffee, drinks, snacks, or recommendations, ALWAYS call `tool_get_menu(query=...)` to retrieve menu items relevant to the customer's request.
   - ONLY recommend items explicitly returned by `tool_get_menu()` for the current turn.
   - NEVER recommend or mention items from general knowledge, outside brands, or previous turns.

2. Vague Queries:
   - If the customer's query is vague or ambiguous (e.g. "something nice", "surprise me", "what do you recommend", "help me choose"), do NOT guess or call `tool_get_menu()` blindly.
   - Instead, ask exactly ONE clarifying question to understand their preferences (e.g. "Do you prefer something hot or cold, and do you like your coffee sweet or strong?").

3. Hard Constraints (Dietary, Allergens, Caffeine, Temperature):
   - When the customer states a hard constraint (e.g. dairy-free, vegan, sugar-free, decaf, or allergies like nuts, gluten, dairy):
     * You MUST verify the actual `tags` and `allergens` fields in the items returned by `tool_get_menu()` before recommending them.
     * Semantic similarity alone does NOT guarantee a constraint is satisfied.
     * If none of the retrieved items satisfy the hard constraint, state so honestly rather than recommending the closest semantic match.

4. Unmatched & Unavailable Food/Drink Items:
   - If `tool_get_menu()` returns zero items, or none of the returned items are actually relevant to what the customer asked for (e.g. bubble tea, matcha frappuccino, pizza, sushi, or alcoholic drinks):
     * Reply with: "Sorry, that's not available on our menu right now."
     * Do NOT invent suggestions, do NOT recommend an unrelated item just to have something to say, and do NOT apologize at length. Be short, honest, and optionally offer to help find something else that is on our menu.

5. Store FAQs, Policies & Operations:
   - When the customer asks about store policies, FAQs, Wi-Fi password, refund/cancellation policies, BYO cup discount, pets, seating, power outlets, bulk/catering orders, store hours, or location:
     * Answer directly, accurately, and politely using the Store Knowledge Base.
     * NEVER reply with "Sorry, that's not available on our menu right now" for store policy, FAQ, Wi-Fi, or hours questions! That response is strictly reserved for non-existent food/drink items.

6. Product Details & Formatting:
   - Format all responses clearly using Markdown with bullet points and bold headers.
   - Include prices in INR (₹) and key attributes (calories, caffeine level, allergens).
"""

# Initialize Official Google ADK Agent Instance
brewbuddy_adk_agent = Agent(
    name="BrewBuddy_ADK_Agent",
    model="gemini-flash-latest",
    description="Customer-facing Coffee Shop Assistant Agent built with Google ADK and Pinecone Vector RAG",
    instruction=SYSTEM_INSTRUCTION,
    tools=[
        tool_get_menu,
        tool_get_product_details,
        tool_check_allergens,
        tool_get_store_information,
        tool_create_order,
        tool_get_current_order,
        tool_update_order,
        tool_remove_from_order,
        tool_clear_order
    ]
)

FAQ_RESPONSES = {
    'refund': """### 📋 **Refund & Cancellation Policy**
* **Cancellation:** Prepared orders cannot be cancelled once brewing or preparation has begun.
* **Replacement & Refund:** If you receive an incorrect, spilled, or defective order, notify our counter staff or assistant immediately.
* **Resolution:** We provide an **immediate counter replacement** or a **100% refund** credited to your original payment method within **24 hours**.""",

    'byo': """### 🌿 **BYO Cup & Sustainability Discount**
* **Instant Discount:** Bring your own clean reusable cup, mug, or tumbler and receive an **instant ₹15 discount** on any espresso, coffee, or cold beverage!
* **Eco Packaging:** All our takeout cups, lids, and packaging are **100% biodegradable and eco-friendly**.""",

    'wifi': """### 📶 **Wi-Fi, Seating & Power Outlets**
* **Network Name (SSID):** `BrewBuddy_Guest`
* **Wi-Fi Password:** `brewbuddycoffee` (Free high-speed fiber internet for all customers)
* **Work Tables:** Dedicated laptop-friendly work tables equipped with AC power outlets and charging ports.
* **Seating Policy:** Dedicated to paying customers. During peak rush hours (8:00–10:00 AM & 4:00–7:00 PM), seating is limited to **2 hours**.""",

    'pets': """### 🐾 **Pet & Dog-Friendly Seating**
* **Pet Policy:** Pets and dogs are warmly welcomed in our outdoor garden and patio seating area!
* **Amenities:** Fresh water bowls are provided free of charge upon request for your furry companions.""",

    'catering': """### 👥 **Bulk & Catering Orders**
* **Advance Notice:** Orders exceeding 10 items require at least **2 hours advance notice** so our baristas can prepare everything fresh.
* **Bulk Discount:** Enjoy an instant **10% discount** on all corporate, party, or bulk catering orders exceeding **₹2,000**!""",

    'allergens': """### 🥛 **Dairy-Free Options & Allergen Notice**
* **Dairy-Free Milk:** We offer **Oat Milk (+₹30)** and **Almond Milk (+₹30)** for any espresso, latte, or iced beverage (Skim milk +₹0).
* **Vegan Options:** Our **Veg Sandwich** on artisanal sourdough is 100% vegan and dairy-free.
* **Cross-Contamination Disclaimer:** All beverages are crafted on shared espresso bar equipment. Please notify our staff of severe nut, dairy, or gluten allergies before placing your order!""",

    'hours': """### ⏰ **Store Hours & Location**
* **Address:** 42 Roasters Lane, Tech District, Bangalore
* **Operating Hours:** Monday to Sunday: **7:00 AM – 10:00 PM** (Kitchen closes at 9:30 PM)."""
}

FAQ_INTENTS = [
    ('refund', [r'\b(refund|refunds|cancel|cancelled|cancellation|return|returns|defective|spilled|wrong order|replacement)\b']),
    ('byo', [r'\b(byo|own cup|reusable|mug|mugs|tumbler|thermos|bring.*cup|bring.*mug)\b']),
    ('wifi', [r'\b(wifi|wi-fi|internet|password|laptop|laptops|outlet|outlets|power|plug|plugs|charging|seating|seats|chair|chairs|work table)\b']),
    ('pets', [r'\b(pet|pets|dog|dogs|cat|cats|animal|animals|patio|water bowl)\b']),
    ('catering', [r'\b(bulk|catering|corporate|party|event|large order|catering order)\b']),
    ('allergens', [r'\b(dairy-free|dairy free|allergen|allergens|allergy|allergies|lactose|gluten|cross-contamination|contamination|nut allergy|nut allergies|oat milk|almond milk|milk alternative|milk alternatives)\b']),
    ('hours', [r'\b(hours|timing|timings|open at|close at|opening|closing|when do you open|when do you close|what time|operating hours|location|address|where are you|where is the|bangalore)\b'])
]

def get_faq_answer(query: str) -> tuple[Optional[str], Optional[str]]:
    q_lower = query.lower()
    for topic, patterns in FAQ_INTENTS:
        if any(re.search(p, q_lower) for p in patterns):
            return topic, FAQ_RESPONSES[topic]
    return None, None


def format_rag_fallback_response(raw_context: str) -> str:
    """Format raw RAG text into clean, Gemini-style markdown with bullet points and bold headers."""
    if not raw_context.strip():
        return "I'm BrewBuddy! I can recommend coffee based on your preferences, answer store policies, or place your order. How can I help you today?"
    
    sections = raw_context.split("---")
    formatted_chunks = []
    
    for sec in sections:
        sec_clean = sec.strip()
        if not sec_clean:
            continue
        
        # Format Q: ... A: ...
        q_a_match = re.search(r'Q:\s*(.*?)\n\s*A:\s*(.*)', sec_clean, flags=re.DOTALL)
        if q_a_match:
            question = q_a_match.group(1).strip()
            answer = q_a_match.group(2).strip()
            formatted_chunks.append(f"### 📋 {question}\n{answer}")
            continue

        lines = sec_clean.split("\n")
        header = lines[0].strip().rstrip(":")
        body_lines = [f"* {l.strip().lstrip('-*').strip()}" for l in lines[1:] if l.strip()]
        if body_lines:
            formatted_chunks.append(f"### 📋 {header}\n" + "\n".join(body_lines))
        else:
            formatted_chunks.append(sec_clean)

    return "\n\n".join(formatted_chunks[:2])

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
        items_md.append(f"* ☕ **{p['name']}** (₹{p['price']}) — {p['description']} (*{p.get('caffeine', 'medium').capitalize()} caffeine, {p.get('calories', 100)} kcal*)")
    
    return "Here are our **best recommendations**:\n\n" + "\n".join(items_md) + "\n\nWhich one would you like to view details or add to your order?"


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

    # Handle direct cart actions ONLY when a specific product from our menu is mentioned
    is_cart_action = False
    if matched_product and any(k in msg_lower for k in ["add to order", "add to cart", "add it", "order this", "order a", "order the"]):
        is_cart_action = True
        tool_called = "add_to_order"
        for word in msg_lower.split():
            if word.isdigit():
                action_qty = int(word)
        add_to_order(session_id, matched_product["name"], quantity=action_qty)

    elif "remove" in msg_lower or "delete" in msg_lower:
        if matched_product:
            is_cart_action = True
            tool_called = "remove_from_order"
            remove_from_order(session_id, matched_product["name"])

    elif "clear" in msg_lower and "order" in msg_lower:
        is_cart_action = True
        tool_called = "clear_order"
        clear_order(session_id)

    # Check if query is specifically about store policies, FAQs, Wi-Fi, hours, etc.
    faq_topic, exact_faq_response = get_faq_answer(message)
    is_faq_query = bool(faq_topic) or any(
        k in msg_lower for k in [
            "policy", "policies", "refund", "cancel", "wifi", "wi-fi", "internet",
            "password", "byo", "pet", "pets", "catering", "bulk", "allergen",
            "allergy", "dairy-free", "hours", "location", "address", "faq"
        ]
    )
    
    rag_context = exact_faq_response if exact_faq_response else (retriever.retrieve(message) if is_faq_query else "")

    # Official Google ADK Agent Execution Loop with High-Speed Vector RAG
    reply = None
    if api_key and not is_cart_action:
        try:
            from backend.rag.pinecone_client import get_genai_client
            client = get_genai_client()
            
            # Sub-millisecond pre-retrieval from Pinecone vector cache
            retrieved_menu = get_menu(message) if not is_faq_query else ""
            
            prompt_parts = []
            if is_faq_query and rag_context:
                prompt_parts.append(f"Store Knowledge Base (Store Policies, FAQs, Wi-Fi, BYO Cup, Pets, Catering, Hours):\n{rag_context}")

            if retrieved_menu and "no relevant menu items found" not in retrieved_menu:
                prompt_parts.append(f"Retrieved Menu Items from Pinecone Vector Search:\n{retrieved_menu}")
            elif "no relevant menu items found" in retrieved_menu and not is_faq_query:
                prompt_parts.append("Pinecone Vector Search Result: No menu items found matching the customer query.")
            
            if history_context:
                prompt_parts.append(f"Recent History:\n{history_context}")
            
            prompt_parts.append(f"Customer Query: {message}")
            full_prompt = "\n\n".join(prompt_parts)
            
            config = types.GenerateContentConfig(
                system_instruction=brewbuddy_adk_agent.instruction,
                temperature=0.2,
                max_output_tokens=350,
                thinking_config=types.ThinkingConfig(thinking_budget=0)
            )
            
            candidate_models = ["gemini-flash-latest", "gemini-3.5-flash", "gemini-2.5-flash"]
            for model_name in candidate_models:
                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=full_prompt,
                        config=config
                    )
                    if response and response.text and response.text.strip():
                        reply = response.text.strip()
                        break
                except Exception:
                    continue
            
            if reply:
                # Extract any recommended products for UI rendering
                for p in all_prods:
                    if p["name"].lower() in reply.lower():
                        if p not in recommended_products:
                            recommended_products.append(p)
                
                save_chat_message(session_id, "assistant", reply)
                current_order = get_order(session_id)
                return {
                    "response": reply,
                    "recommended_products": recommended_products[:3],
                    "order": current_order,
                    "tool_called": "tool_get_store_information" if is_faq_query else "tool_get_menu"
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
    elif is_faq_query:
        # High quality grounded FAQ response
        reply = exact_faq_response if exact_faq_response else format_rag_fallback_response(rag_context)
        tool_called = "tool_get_store_information"
    else:
        # Fallback to direct Pinecone search if API is unavailable
        try:
            menu_res = json.loads(get_menu(message))
            items = menu_res.get("items", [])
            # Require high confidence for recommendation fallback
            if items and items[0].get("similarity_score", items[0].get("score", 0)) >= 0.62:
                reply = format_recommendations_response(items)
                recommended_products = [get_product_by_id_or_name(it["name"]) for it in items[:3] if get_product_by_id_or_name(it["name"])]
            else:
                reply = "Sorry, that's not available on our menu right now. Would you like to try one of our specialty coffees or teas?"
        except Exception:
            reply = "I'm **BrewBuddy**! I can recommend beverages based on your taste, caffeine, and dietary preferences, check ingredients & allergens, or take your order. How can I help you today?"

    save_chat_message(session_id, "assistant", reply)

    return {
        "response": reply,
        "recommended_products": recommended_products,
        "order": current_order,
        "tool_called": tool_called
    }
