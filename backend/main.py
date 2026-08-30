import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from backend.models.schemas import (
    ChatRequest, ChatResponse, OrderActionRequest, OrderResponse, PreferenceModel
)
from backend.services.db import (
    init_db, get_all_products, get_product_by_id_or_name,
    get_chat_history, clear_chat_history
)
from backend.services.order_service import (
    get_order, add_to_order, update_order_item, remove_from_order, clear_order
)
from backend.services.recommendation import recommend_products
from backend.agent.agent import process_chat_message

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(title="BrewBuddy AI API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
def health_check():
    return {"status": "healthy", "service": "BrewBuddy AI", "version": "1.0.0"}

@app.get("/api/menu")
def list_menu():
    return get_all_products()

@app.get("/api/menu/{product_id}")
def get_product(product_id: str):
    product = get_product_by_id_or_name(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product

@app.post("/api/chat", response_model=ChatResponse)
def chat_endpoint(request: ChatRequest):
    prefs_dict = request.preferences.model_dump() if request.preferences else {}
    res = process_chat_message(
        message=request.message,
        session_id=request.session_id or "default_user",
        preferences=prefs_dict
    )
    return res

@app.get("/api/chat/history")
def get_chat_history_endpoint(session_id: str = "default_user"):
    return get_chat_history(session_id)

@app.delete("/api/chat/history")
def clear_chat_history_endpoint(session_id: str = "default_user"):
    clear_chat_history(session_id)
    return {"status": "cleared", "session_id": session_id}

@app.post("/api/recommend")
def recommend_endpoint(preferences: PreferenceModel):
    return recommend_products(preferences.model_dump())

@app.get("/api/order", response_model=OrderResponse)
def get_order_endpoint(session_id: str = "default_user"):
    return get_order(session_id)

@app.post("/api/order", response_model=OrderResponse)
def add_to_order_endpoint(request: OrderActionRequest, session_id: str = "default_user"):
    try:
        return add_to_order(
            session_id=session_id,
            product_name=request.product_name,
            quantity=request.quantity,
            customization=request.customization
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.put("/api/order", response_model=OrderResponse)
def update_order_endpoint(request: OrderActionRequest, session_id: str = "default_user"):
    return update_order_item(
        session_id=session_id,
        product_name=request.product_name,
        quantity=request.quantity
    )

@app.delete("/api/order/{product_name}", response_model=OrderResponse)
def delete_order_item_endpoint(product_name: str, session_id: str = "default_user"):
    return remove_from_order(session_id=session_id, product_name=product_name)

@app.delete("/api/order", response_model=OrderResponse)
def clear_order_endpoint(session_id: str = "default_user"):
    return clear_order(session_id=session_id)

frontend_dir = os.path.join(os.path.dirname(__file__), "../frontend")
if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
