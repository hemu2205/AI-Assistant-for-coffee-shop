from typing import Dict, Any, List
from backend.services.db import get_db_connection, get_product_by_id_or_name

TAX_RATE = 0.05  # 5% GST

def get_order(session_id: str) -> Dict[str, Any]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM order_items WHERE session_id = ?", (session_id,))
    rows = cursor.fetchall()
    conn.close()

    items = []
    subtotal = 0.0
    for r in rows:
        item_total = r["unit_price"] * r["quantity"]
        subtotal += item_total
        items.append({
            "product_id": r["product_id"],
            "product_name": r["product_name"],
            "quantity": r["quantity"],
            "unit_price": r["unit_price"],
            "customization": r["customization"]
        })

    tax = round(subtotal * TAX_RATE, 2)
    total = round(subtotal + tax, 2)

    return {
        "items": items,
        "subtotal": round(subtotal, 2),
        "tax_rate": TAX_RATE,
        "tax": tax,
        "total": total
    }

def add_to_order(session_id: str, product_name: str, quantity: int = 1, customization: str = None) -> Dict[str, Any]:
    product = get_product_by_id_or_name(product_name)
    if not product:
        raise ValueError(f"Product '{product_name}' not found in menu.")

    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT id, quantity FROM order_items WHERE session_id = ? AND product_id = ?",
        (session_id, product["id"])
    )
    existing = cursor.fetchone()

    if existing:
        new_qty = existing["quantity"] + quantity
        cursor.execute("UPDATE order_items SET quantity = ? WHERE id = ?", (new_qty, existing["id"]))
    else:
        cursor.execute(
            "INSERT INTO order_items (session_id, product_id, product_name, quantity, unit_price, customization) VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, product["id"], product["name"], quantity, product["price"], customization)
        )
    
    conn.commit()
    conn.close()
    return get_order(session_id)

def update_order_item(session_id: str, product_name: str, quantity: int) -> Dict[str, Any]:
    product = get_product_by_id_or_name(product_name)
    if not product:
        raise ValueError(f"Product '{product_name}' not found.")

    conn = get_db_connection()
    cursor = conn.cursor()
    if quantity <= 0:
        cursor.execute("DELETE FROM order_items WHERE session_id = ? AND product_id = ?", (session_id, product["id"]))
    else:
        cursor.execute("UPDATE order_items SET quantity = ? WHERE session_id = ? AND product_id = ?", (quantity, session_id, product["id"]))
    conn.commit()
    conn.close()
    return get_order(session_id)

def remove_from_order(session_id: str, product_name: str) -> Dict[str, Any]:
    return update_order_item(session_id, product_name, quantity=0)

def clear_order(session_id: str) -> Dict[str, Any]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM order_items WHERE session_id = ?", (session_id,))
    conn.commit()
    conn.close()
    return get_order(session_id)
