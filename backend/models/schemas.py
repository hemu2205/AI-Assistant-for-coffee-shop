from typing import List, Optional
from pydantic import BaseModel, Field

class PreferenceModel(BaseModel):
    temperature: Optional[str] = Field(default=None, description="hot, cold, or any")
    sweetness: Optional[str] = Field(default=None, description="none, low, medium, high")
    caffeine: Optional[str] = Field(default=None, description="high, medium, low, none")
    milk: Optional[str] = Field(default="whole", description="whole, skim, oat, almond, none")
    diet: Optional[str] = Field(default=None, description="vegan, vegetarian, dairy-free, keto")
    budget: Optional[float] = Field(default=500.0, description="Maximum budget in INR")

class Product(BaseModel):
    id: str
    name: str
    category: str
    description: str
    price: float
    image_url: Optional[str] = None
    ingredients: List[str]
    caffeine: str
    sweetness: str
    temperature: str
    milk_options: List[str]
    dietary_tags: List[str]
    allergens: List[str]
    calories: int

class OrderItem(BaseModel):
    product_id: str
    product_name: str
    quantity: int = 1
    unit_price: float
    customization: Optional[str] = None

class OrderResponse(BaseModel):
    items: List[OrderItem]
    subtotal: float
    tax_rate: float = 0.05
    tax: float
    total: float

class OrderActionRequest(BaseModel):
    product_name: str
    quantity: int = 1
    customization: Optional[str] = None

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = "default_user"
    preferences: Optional[PreferenceModel] = None

class ChatResponse(BaseModel):
    response: str
    recommended_products: List[Product] = []
    order: Optional[OrderResponse] = None
    tool_called: Optional[str] = None
