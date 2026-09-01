from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional, Any, Dict
from backend.app.services.event_service import event_service
from backend.app.models.event import Event

router = APIRouter(prefix="/api/events", tags=["Events"])

@router.get("", response_model=List[Event])
def get_events(
    process_id: Optional[int] = Query(None, description="Filter by process ID"),
    order_id: Optional[int] = Query(None, description="Filter by order ID")
):
    return event_service.get_events(process_id=process_id, order_id=order_id)

@router.get("/compare")
def compare_events(
    event_a: str = Query(..., description="First event ID (e.g. E10)"),
    event_b: str = Query(..., description="Second event ID (e.g. E14)")
):
    try:
        return event_service.compare_events(event_a, event_b)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/{event_id}", response_model=Event)
def get_event(event_id: str):
    ev = event_service.get_event(event_id)
    if not ev:
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found")
    return ev
