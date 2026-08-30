import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.services.db import init_db

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_database():
    init_db()

def test_health():
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "healthy"

def test_menu_list():
    res = client.get("/api/menu")
    assert res.status_code == 200
    items = res.json()
    assert len(items) >= 15

def test_order_creation_and_calculation():
    client.delete("/api/order")
    res = client.post("/api/order", json={"product_name": "Iced Latte", "quantity": 2})
    assert res.status_code == 200
    cart = res.json()
    assert len(cart["items"]) == 1
    assert cart["subtotal"] == 500.0
    assert cart["tax"] == 25.0
    assert cart["total"] == 525.0

def test_recommendation_engine():
    res = client.post("/api/recommend", json={"temperature": "cold", "sweetness": "low", "caffeine": "high"})
    assert res.status_code == 200
    products = res.json()
    assert len(products) > 0
    assert products[0]["temperature"] == "cold"
