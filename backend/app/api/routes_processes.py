from fastapi import APIRouter, HTTPException
from typing import List, Dict
from backend.app.services.process_service import process_service
from backend.app.models.process import ProcessState

router = APIRouter(prefix="/api/processes", tags=["Processes"])

@router.get("", response_model=List[ProcessState])
def get_processes():
    return process_service.get_all_processes()

@router.get("/{process_id}", response_model=ProcessState)
def get_process(process_id: int):
    proc = process_service.get_process(process_id)
    if not proc:
        raise HTTPException(status_code=404, detail=f"Process P{process_id} not found")
    return proc

@router.get("/{process_id}/vector-clock")
def get_process_vector_clock(process_id: int):
    proc = process_service.get_process(process_id)
    if not proc:
        raise HTTPException(status_code=404, detail=f"Process P{process_id} not found")
    return {"process_id": process_id, "vector_clock": proc.vector_clock}

@router.post("/reset")
async def reset_processes():
    await process_service.reset_all()
    return {"status": "SUCCESS", "message": "All processes reset to initial state"}
