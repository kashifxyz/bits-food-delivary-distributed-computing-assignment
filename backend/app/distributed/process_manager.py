import asyncio
import json
import logging
import os
from typing import Dict, List, Optional
from backend.app.config.settings import settings
from backend.app.distributed.process import DistributedProcess
from backend.app.distributed.message_bus import LocalMessageBus, MessageBus
from backend.app.distributed.event_manager import EventManager, event_manager
from backend.app.snapshot.snapshot_manager import SnapshotManager
from backend.app.models.process import ProcessConfig, ProcessStatus, ProcessState

logger = logging.getLogger("ProcessManager")

class ProcessManager:
    """
    Coordinator and lifecycle manager for all distributed processes (P1-P4).
    Wires communication topology, async channel consumers, and Chandy-Lamport snapshot manager.
    """
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or settings.PROCESS_CONFIG_PATH
        self.event_manager: EventManager = event_manager
        self.processes: Dict[int, DistributedProcess] = {}
        self.message_bus: MessageBus = LocalMessageBus(process_ids=[1, 2, 3, 4])
        self.snapshot_manager = SnapshotManager(process_manager=self)
        
        self._consumer_tasks: List[asyncio.Task] = []
        self._is_running = False
        
        self._load_and_init_processes()

    def _load_and_init_processes(self):
        process_configs = [
            {"id": 1, "name": "P1", "role": "Order Processor", "desc": "Coordinates order lifecycle and assigns dispatch"},
            {"id": 2, "name": "P2", "role": "Restaurant A", "desc": "Kitchen processing orders and preparing food"},
            {"id": 3, "name": "P3", "role": "Delivery Partner", "desc": "Accepts delivery tasks and delivers food to customer"},
            {"id": 4, "name": "P4", "role": "Restaurant B", "desc": "Independent restaurant and concurrent event generator"}
        ]
        
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r") as f:
                    data = json.load(f)
                    if "processes" in data:
                        process_configs = [
                            {"id": p["id"], "name": p["name"], "role": p["role"], "desc": p.get("description", "")}
                            for p in data["processes"]
                        ]
            except Exception as e:
                logger.warning(f"Could not load process config from {self.config_path}, using defaults: {e}")

        for cfg in process_configs:
            pid = cfg["id"]
            proc = DistributedProcess(
                process_id=pid,
                name=cfg["name"],
                role=cfg["role"],
                description=cfg["desc"],
                num_processes=len(process_configs),
                message_bus=self.message_bus,
                event_mgr=self.event_manager
            )
            proc.set_snapshot_manager(self.snapshot_manager)
            self.processes[pid] = proc

    def get_process(self, process_id: int) -> Optional[DistributedProcess]:
        return self.processes.get(process_id)

    def get_all_processes(self) -> List[DistributedProcess]:
        return list(self.processes.values())

    def get_all_process_states(self) -> List[ProcessState]:
        return [p.get_state() for p in self.processes.values()]

    async def start(self):
        """Starts asynchronous background channel listeners for each directed channel."""
        if self._is_running:
            return
            
        self._is_running = True
        logger.info("Starting ProcessManager and async channel listeners...")
        
        all_channels = self.message_bus.get_all_channels()
        for ch_key, channel in all_channels.items():
            task = asyncio.create_task(self._channel_listener(channel))
            self._consumer_tasks.append(task)

    async def _channel_listener(self, channel):
        """Dedicated consumer worker for a directed channel."""
        receiver_id = channel.receiver_id
        while self._is_running:
            try:
                message = await channel.receive()
                receiver = self.get_process(receiver_id)
                if receiver:
                    await receiver.receive_msg(message)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in channel listener {channel.channel_key}: {e}")

    async def stop(self):
        self._is_running = False
        for task in self._consumer_tasks:
            task.cancel()
        if self._consumer_tasks:
            await asyncio.gather(*self._consumer_tasks, return_exceptions=True)
        self._consumer_tasks.clear()

    async def reset(self):
        await self.stop()
        self.message_bus = LocalMessageBus(process_ids=list(self.processes.keys()))
        for proc in self.processes.values():
            proc.reset()
            proc.set_message_bus(self.message_bus)
        self.event_manager.clear()
        self.snapshot_manager.reset()
        await self.start()
        logger.info("ProcessManager reset successfully.")

process_manager = ProcessManager()
