from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
from backend.app.simulation.simulator import Simulator
from backend.app.distributed.process_manager import process_manager

router = APIRouter(prefix="/api/scenarios", tags=["Scenarios"])
simulator = Simulator(process_manager)

@router.get("")
def get_scenarios():
    return simulator.get_scenarios()

@router.post("/{scenario_id}/run")
async def run_scenario(scenario_id: str):
    try:
        return await simulator.run_scenario(scenario_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scenario execution failed: {str(e)}")
