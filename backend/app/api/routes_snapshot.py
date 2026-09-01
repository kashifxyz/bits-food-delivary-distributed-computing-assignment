from fastapi import APIRouter, HTTPException, Body
from typing import List
from backend.app.services.snapshot_service import snapshot_service
from backend.app.models.snapshot import GlobalSnapshot, ConsistencyCheckResult

router = APIRouter(prefix="/api/snapshots", tags=["Snapshots"])

@router.post("", response_model=GlobalSnapshot)
async def initiate_snapshot(initiator_id: int = Body(default=1, embed=True)):
    try:
        return await snapshot_service.initiate_snapshot(initiator_id=initiator_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Snapshot failed: {str(e)}")

@router.get("", response_model=List[GlobalSnapshot])
def get_all_snapshots():
    return snapshot_service.get_all_snapshots()

@router.get("/{snapshot_id}", response_model=GlobalSnapshot)
def get_snapshot(snapshot_id: str):
    snap = snapshot_service.get_snapshot(snapshot_id)
    if not snap:
        raise HTTPException(status_code=404, detail=f"Snapshot {snapshot_id} not found")
    return snap

@router.get("/{snapshot_id}/consistency", response_model=ConsistencyCheckResult)
def check_snapshot_consistency(snapshot_id: str):
    res = snapshot_service.check_consistency(snapshot_id)
    if not res:
        raise HTTPException(status_code=404, detail=f"Snapshot {snapshot_id} not found")
    return res
