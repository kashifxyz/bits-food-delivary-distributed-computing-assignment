import pytest
import asyncio
from backend.app.distributed.process_manager import ProcessManager
from backend.app.simulation.scenarios import ScenarioRunner

@pytest.mark.asyncio
async def test_full_order_flow():
    pm = ProcessManager()
    await pm.start()
    
    runner = ScenarioRunner(pm)
    result = await runner.run_tc01_basic_order_flow(order_id=105)
    
    assert result["status"] == "SUCCESS"
    assert result["order_id"] == 105
    
    # Check that events were generated in the global event manager
    events = pm.event_manager.get_all_events()
    assert len(events) >= 6
    
    # Verify vector clock advancement
    p1 = pm.get_process(1)
    p3 = pm.get_process(3)
    assert p1.vector_clock.get_clock()[0] >= 2
    assert p3.vector_clock.get_clock()[2] >= 1
    
    await pm.stop()
