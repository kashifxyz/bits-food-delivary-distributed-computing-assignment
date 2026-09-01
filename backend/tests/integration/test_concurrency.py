import pytest
import asyncio
from backend.app.distributed.process_manager import ProcessManager
from backend.app.simulation.scenarios import ScenarioRunner

@pytest.mark.asyncio
async def test_concurrent_events_scenario():
    pm = ProcessManager()
    await pm.start()
    
    runner = ScenarioRunner(pm)
    result = await runner.run_tc03_concurrent_events()
    
    assert result["status"] == "SUCCESS"
    assert result["relation"] == "CONCURRENT"
    assert "concurrently without causal dependency" in result["explanation"]
    
    await pm.stop()
