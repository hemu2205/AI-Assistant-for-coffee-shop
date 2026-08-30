import sqlite3
import json
import os
from typing import List, Dict, Any, Optional

if os.getenv("VERCEL"):
    DB_PATH = "/tmp/brewbuddy.db"
else:
    DB_PATH = os.path.join(os.path.dirname(__file__), "../../brewbuddy.db")
DATA_MENU_PATH = os.path.join(os.path.dirname(__file__), "../../data/menu.json")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Products Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            description TEXT,
            price REAL NOT NULL,
            image_url TEXT,
            ingredients TEXT,
            caffeine TEXT,
            sweetness TEXT,
            temperature TEXT,
            milk_options TEXT,
            dietary_tags TEXT,
            allergens TEXT,
            calories INTEGER
        )
    ''')

    # Orders Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            product_id TEXT NOT NULL,
            product_name TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            unit_price REAL NOT NULL,
            customization TEXT
        )
    ''')

    # Persistent Chat History Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            message TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute("PRAGMA table_info(products)")
    columns = [col[1] for col in cursor.fetchall()]
    if "image_url" not in columns:
        cursor.execute("ALTER TABLE products ADD COLUMN image_url TEXT")

    if os.path.exists(DATA_MENU_PATH):
        with open(DATA_MENU_PATH, "r", encoding="utf-8") as f:
            items = json.load(f)
            for item in items:
                cursor.execute('''
                    INSERT OR REPLACE INTO products (
                        id, name, category, description, price, image_url,
                        ingredients, caffeine, sweetness, temperature,
                        milk_options, dietary_tags, allergens, calories
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    item["id"],
                    item["name"],
                    item["category"],
                    item["description"],
                    item["price"],
                    item.get("image_url", ""),
                    json.dumps(item["ingredients"]),
                    item["caffeine"],
                    item["sweetness"],
                    item["temperature"],
                    json.dumps(item["milk_options"]),
                    json.dumps(item["dietary_tags"]),
                    json.dumps(item["allergens"]),
                    item["calories"]
                ))
    conn.commit()
    conn.close()

def get_all_products() -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products")
    rows = cursor.fetchall()
    conn.close()
    
    products = []
    for row in rows:
        item = dict(row)
        item["ingredients"] = json.loads(item["ingredients"]) if isinstance(item["ingredients"], str) else item["ingredients"]
        item["milk_options"] = json.loads(item["milk_options"]) if isinstance(item["milk_options"], str) else item["milk_options"]
        item["dietary_tags"] = json.loads(item["dietary_tags"]) if isinstance(item["dietary_tags"], str) else item["dietary_tags"]
        item["allergens"] = json.loads(item["allergens"]) if isinstance(item["allergens"], str) else item["allergens"]
        products.append(item)
    return products

def get_product_by_id_or_name(query: str) -> Optional[Dict[str, Any]]:
    products = get_all_products()
    query_lower = query.lower().strip()
    for p in products:
        if p["id"].lower() == query_lower or p["name"].lower() == query_lower:
            return p
    for p in products:
        if query_lower in p["name"].lower():
            return p
    return None

# Chat History Operations
def save_chat_message(session_id: str, role: str, message: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO chat_history (session_id, role, message) VALUES (?, ?, ?)",
        (session_id, role, message)
    )
    conn.commit()
    conn.close()

def get_chat_history(session_id: str, limit: int = 50) -> List[Dict[str, str]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT role, message FROM chat_history WHERE session_id = ? ORDER BY id ASC LIMIT ?",
        (session_id, limit)
    )
    rows = cursor.fetchall()
    conn.close()
    return [{"role": r["role"], "message": r["message"]} for r in rows]

def clear_chat_history(session_id: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM chat_history WHERE session_id = ?", (session_id,))
    conn.commit()
    conn.close()
