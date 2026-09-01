from typing import List, Optional, Dict, Any
from backend.app.distributed.process_manager import process_manager
from backend.app.models.process import ProcessState, ProcessStatus

class ProcessService:
    def __init__(self, pm=process_manager):
        self.pm = pm

    def get_all_processes(self) -> List[ProcessState]:
        return self.pm.get_all_process_states()

    def get_process(self, process_id: int) -> Optional[ProcessState]:
        proc = self.pm.get_process(process_id)
        return proc.get_state() if proc else None

    def get_vector_clocks(self) -> Dict[str, List[int]]:
        return {p.name: p.vector_clock.get_clock() for p in self.pm.get_all_processes()}

    async def reset_all(self):
        await self.pm.reset()

process_service = ProcessService()
