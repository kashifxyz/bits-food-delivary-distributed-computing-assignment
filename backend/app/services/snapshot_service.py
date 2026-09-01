from typing import List, Optional, Dict, Any
from backend.app.distributed.process_manager import process_manager
from backend.app.models.snapshot import GlobalSnapshot, ConsistencyCheckResult
from backend.app.snapshot.consistency import ConsistencyChecker

class SnapshotService:
    def __init__(self, pm=process_manager):
        self.pm = pm

    async def initiate_snapshot(self, initiator_id: int = 1) -> GlobalSnapshot:
        return await self.pm.snapshot_manager.initiate_snapshot(initiator_id=initiator_id)

    def get_all_snapshots(self) -> List[GlobalSnapshot]:
        return self.pm.snapshot_manager.get_all_snapshots()

    def get_snapshot(self, snapshot_id: str) -> Optional[GlobalSnapshot]:
        return self.pm.snapshot_manager.get_snapshot(snapshot_id)

    def check_consistency(self, snapshot_id: str) -> Optional[ConsistencyCheckResult]:
        snap = self.get_snapshot(snapshot_id)
        if not snap:
            return None
        events = self.pm.event_manager.get_all_events()
        return ConsistencyChecker.verify(snap, events)

snapshot_service = SnapshotService()
