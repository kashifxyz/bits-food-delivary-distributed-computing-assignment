import logging
from typing import Dict, Any, List
from backend.app.simulation.scenarios import ScenarioRunner

logger = logging.getLogger("Simulator")

class Simulator:
    """
    Simulation orchestrator exposing scenario runs and demo controls.
    """
    def __init__(self, process_manager):
        self.pm = process_manager
        self.runner = ScenarioRunner(process_manager)
        self._available_scenarios = [
            {
                "id": "tc01_basic_order",
                "name": "TC01 — Basic Order Flow",
                "description": "Demonstrates internal, send, receive events and vector clock propagation across P1 -> P2 -> P3 -> P1."
            },
            {
                "id": "tc02_vector_clock",
                "name": "TC02 — Vector Clock Progression",
                "description": "Demonstrates deterministic clock advancement and causal tracking across processes."
            },
            {
                "id": "tc03_concurrent_events",
                "name": "TC03 — Concurrent Events",
                "description": "Generates independent events at P2 and P4 and verifies concurrent causal relationship."
            },
            {
                "id": "tc04_in_transit_snapshot",
                "name": "TC04 — In-Transit Message Snapshot",
                "description": "Dispatches a message and captures it in the channel state during Chandy-Lamport snapshot."
            },
            {
                "id": "tc05_global_snapshot",
                "name": "TC05 — Global Snapshot & Consistency",
                "description": "Coordinates full distributed activity and captures complete 4-process, 12-channel consistent state."
            }
        ]

    def get_scenarios(self) -> List[Dict[str, Any]]:
        return self._available_scenarios

    async def run_scenario(self, scenario_id: str, **kwargs) -> Dict[str, Any]:
        if scenario_id in ["tc01_basic_order", "basic_order"]:
            return await self.runner.run_tc01_basic_order_flow(order_id=kwargs.get("order_id", 101))
        elif scenario_id in ["tc02_vector_clock", "vector_clock"]:
            return await self.runner.run_tc02_vector_clock_progression()
        elif scenario_id in ["tc03_concurrent_events", "concurrent_events"]:
            return await self.runner.run_tc03_concurrent_events()
        elif scenario_id in ["tc04_in_transit_snapshot", "in_transit_message"]:
            return await self.runner.run_tc04_in_transit_message_snapshot()
        elif scenario_id in ["tc05_global_snapshot", "global_snapshot"]:
            return await self.runner.run_tc05_global_snapshot()
        else:
            raise ValueError(f"Unknown scenario ID: {scenario_id}")
