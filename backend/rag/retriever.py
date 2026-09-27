import os
import re
from typing import List, Dict

DATA_DIR = os.path.join(os.path.dirname(__file__), "../../data")

STOP_WORDS = {
    "tell", "me", "more", "about", "what", "is", "the", "a", "an", "can",
    "you", "details", "show", "give", "have", "do", "info", "information",
    "please", "want", "know", "check", "how", "much", "many", "does", "contains",
    "i", "like", "get", "would", "could", "some", "any", "work"
}

TOPIC_SYNONYMS = {
    "where": ["location", "address", "lane", "bangalore"],
    "located": ["location", "address"],
    "cafe": ["store", "coffee shop", "brewbuddy"],
    "shop": ["store", "brewbuddy"],
    "close": ["closing", "hours", "closes"],
    "closes": ["closing", "hours", "close"],
    "open": ["opening", "hours", "operating", "opens"],
    "opens": ["opening", "hours", "operating", "open"],
    "hours": ["operating", "timings", "hours", "close", "open"],
    "timing": ["hours", "operating", "timings"],
    "timings": ["hours", "operating", "timing"],
    "cup": ["mug", "reusable", "byo", "discount"],
    "own": ["reusable", "byo", "mug", "cup"],
    "bring": ["reusable", "byo", "cup", "mug"],
    "pets": ["pet", "dog", "dogs", "patio", "water bowl"],
    "pet": ["pets", "dog", "dogs", "patio", "water bowl"],
    "dog": ["pet", "pets", "dogs", "patio"],
    "dogs": ["pet", "pets", "dog", "patio"],
    "wifi": ["wi-fi", "internet", "password", "network"],
    "wi-fi": ["wifi", "internet", "password", "network"],
    "internet": ["wifi", "wi-fi", "password"],
    "password": ["wifi", "wi-fi", "internet", "brewbuddycoffee"],
    "outlet": ["outlets", "power", "plug", "charging"],
    "outlets": ["outlet", "power", "plug", "charging"],
    "plug": ["outlet", "outlets", "power", "charging"],
    "plugs": ["outlet", "outlets", "power", "charging"],
    "charging": ["power", "outlet", "plug"],
    "laptop": ["seating", "table", "outlet", "work"],
    "seat": ["seating", "tables", "patio"],
    "seating": ["seat", "tables", "patio", "limit"],
    "allergen": ["allergens", "allergy", "allergies", "contamination", "dairy", "nut", "gluten"],
    "allergens": ["allergen", "allergy", "allergies", "contamination", "dairy", "nut", "gluten"],
    "allergy": ["allergen", "allergens", "allergies", "dairy", "nut", "gluten"],
    "allergies": ["allergen", "allergens", "allergy", "dairy", "nut", "gluten"],
    "dairy-free": ["dairy", "milk", "oat", "almond", "vegan"],
    "dairy": ["milk", "oat", "almond", "lactose", "dairy-free"],
    "vegan": ["dairy-free", "sandwich", "sourdough"],
    "catering": ["bulk", "corporate", "party", "advance"],
    "bulk": ["catering", "corporate", "advance", "10 items"],
    "refund": ["cancellation", "replacement", "return", "defective", "24 hours"],
    "cancel": ["cancellation", "refund", "cannot be cancelled"],
    "cancellation": ["cancel", "refund", "replacement"],
    "discounts": ["discount", "15", "10%"]
}

class KnowledgeBaseRetriever:
    def __init__(self):
        self.documents: List[Dict[str, str]] = []
        self.load_documents()

    def load_documents(self):
        self.documents = []
        files = ["store_info.txt", "faq.txt", "allergens.txt", "menu.txt"]
        for fname in files:
            fpath = os.path.join(DATA_DIR, fname)
            if os.path.exists(fpath):
                with open(fpath, "r", encoding="utf-8") as f:
                    content = f.read()
                    paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
                    for p in paragraphs:
                        self.documents.append({
                            "source": fname,
                            "content": p
                        })

    def retrieve(self, query: str, top_k: int = 3) -> str:
        words = re.findall(r'[a-zA-Z0-9\-_]+', query.lower())
        query_terms = set()
        for w in words:
            if w not in STOP_WORDS and len(w) > 1:
                query_terms.add(w)
                if w in TOPIC_SYNONYMS:
                    query_terms.update(TOPIC_SYNONYMS[w])

        if not query_terms:
            return ""

        scored_docs = []
        for doc in self.documents:
            doc_lower = doc["content"].lower()
            score = 0
            for term in query_terms:
                if term in doc_lower:
                    score += 2 if len(term) > 3 else 1
            if score > 0:
                scored_docs.append((score, doc["content"]))

        if not scored_docs:
            return ""

        scored_docs.sort(key=lambda x: x[0], reverse=True)
        results = [doc[1] for doc in scored_docs[:top_k]]
        return "\n---\n".join(results)

retriever = KnowledgeBaseRetriever()
