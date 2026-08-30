from typing import List, Dict, Any
from backend.services.db import get_all_products

def recommend_products(preferences: Dict[str, Any]) -> List[Dict[str, Any]]:
    products = get_all_products()
    scored_products = []

    temp_pref = (preferences.get("temperature") or "").lower()
    sweet_pref = (preferences.get("sweetness") or "").lower()
    caff_pref = (preferences.get("caffeine") or "").lower()
    diet_pref = (preferences.get("diet") or "").lower()
    budget_pref = preferences.get("budget", 500.0)

    for p in products:
        score = 0
        if p["price"] > budget_pref:
            continue

        if temp_pref and p["temperature"] == temp_pref:
            score += 3
        
        if sweet_pref and p["sweetness"] == sweet_pref:
            score += 3

        if caff_pref and p["caffeine"] == caff_pref:
            score += 3

        if diet_pref:
            if diet_pref in [d.lower() for d in p["dietary_tags"]]:
                score += 4
            elif diet_pref == "dairy-free" and "dairy" not in [a.lower() for a in p["allergens"]]:
                score += 4

        scored_products.append((score, p))

    scored_products.sort(key=lambda x: x[0], reverse=True)
    return [item[1] for item in scored_products[:4]]
