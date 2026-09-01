import pytest
import asyncio
from backend.app.distributed.process_manager import ProcessManager
from backend.app.simulation.scenarios import ScenarioRunner

@pytest.mark.asyncio
async def test_global_snapshot_scenario():
    pm = ProcessManager()
    await pm.start()
    
    runner = ScenarioRunner(pm)
    result = await runner.run_tc05_global_snapshot()
    
    assert result["status"] == "SUCCESS"
    assert result["snapshot_id"].startswith("SNAP-")
    assert result["process_states_count"] == 4
    assert result["consistency"] is not None
    assert result["consistency"]["consistent"] is True
    
    await pm.stop()
