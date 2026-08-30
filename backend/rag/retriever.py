import os
import re
from typing import List, Dict

DATA_DIR = os.path.join(os.path.dirname(__file__), "../../data")

STOP_WORDS = {
    "tell", "me", "more", "about", "what", "is", "the", "a", "an", "can",
    "you", "details", "show", "give", "have", "do", "info", "information",
    "please", "want", "know", "check", "how", "much", "many", "does", "contains"
}

class KnowledgeBaseRetriever:
    def __init__(self):
        self.documents: List[Dict[str, str]] = []
        self.load_documents()

    def load_documents(self):
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
        all_words = set(re.findall(r'\w+', query.lower()))
        meaningful_words = all_words - STOP_WORDS
        target_words = meaningful_words if meaningful_words else all_words

        if not target_words:
            return ""

        scored_docs = []
        for doc in self.documents:
            doc_words = set(re.findall(r'\w+', doc["content"].lower()))
            overlap = len(target_words.intersection(doc_words))
            if overlap > 0:
                scored_docs.append((overlap, doc["content"]))

        scored_docs.sort(key=lambda x: x[0], reverse=True)
        results = [doc[1] for doc in scored_docs[:top_k]]
        return "\n---\n".join(results)

retriever = KnowledgeBaseRetriever()
