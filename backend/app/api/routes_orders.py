from fastapi import APIRouter, HTTPException, Body
from typing import List, Optional
from backend.app.services.order_service import order_service
from backend.app.models.order import Order

router = APIRouter(prefix="/api/orders", tags=["Orders"])

@router.get("", response_model=List[Order])
def get_orders():
    return order_service.get_all_orders()

@router.get("/{order_id}", response_model=Order)
def get_order(order_id: int):
    order = order_service.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail=f"Order #{order_id} not found")
    return order

@router.post("", response_model=Order)
async def create_order(
    customer: str = Body(default="Customer-1", embed=True),
    restaurant_id: int = Body(default=2, embed=True),
    items: List[str] = Body(default=["Veg Biryani", "Raita"], embed=True)
):
    return await order_service.create_order(customer=customer, restaurant_id=restaurant_id, items=items)

@router.post("/{order_id}/action")
async def trigger_order_action(order_id: int, action: str = Body(..., embed=True)):
    try:
        return await order_service.trigger_order_action(order_id, action)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
